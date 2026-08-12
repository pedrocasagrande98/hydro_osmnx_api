# Planejamento: API hydro_osmnx na Hostinger VPS

Como especialista DevOps, analisei a estrutura do seu projeto atual, que opera como uma aplicação CLI (via `run.py`) executando operações geoespaciais pesadas (GeoPandas, DuckDB Spatial, OSMnx) para cruzar manchas de inundação (GLOFAS) com malhas viárias e hidrografia.

Abaixo está a proposta de arquitetura para transformar esse pipeline em uma API robusta, escalável e adequada às configurações do seu servidor Hostinger:

**Especificações do Servidor (Hostinger VPS):**
- **vCPU:** 2 núcleos
- **RAM:** 8 GB
- **Disco:** 100 GB NVMe
- **Banda:** 8 TB

---

## 1. Arquitetura da Solução

Para converter o script atual (`run.py`) em um serviço consumível por outras aplicações, recomendo a seguinte stack:

*   **Framework API:** **FastAPI** (Python). É extremamente rápido, possui documentação automática (Swagger/OpenAPI) e lida nativamente com tipagem de dados, ideal para receber GeoJSONs e parâmetros (nível de inundação, buffers, etc).
*   **Processamento Assíncrono:** Operações geoespaciais e downloads do OSM podem ser demorados (de segundos a minutos). Uma chamada de API comum (HTTP) pode dar "timeout". 
    *   *Opção Simples:* FastAPI `BackgroundTasks` (ideal para MVP, mas menos resiliente).
    *   *Opção Robusta:* **Celery + Redis**. A API apenas recebe o pedido, coloca na fila (Redis) e retorna um `task_id`. Um *worker* (Celery) faz o processamento no background e o cliente consulta o status depois (Webhooks ou Polling).
*   **Containerização:** **Docker & Docker Compose**. Essencial para aplicações geoespaciais. Bibliotecas como GDAL, GeoPandas e pyproj podem ser muito difíceis de configurar no sistema operacional bruto. Com Docker, você encapsula tudo.
*   **Proxy Reverso e SSL:** **Nginx** atuando como proxy reverso para o FastAPI, juntamente com **Certbot** para gerar certificados SSL (HTTPS) gratuitos da Let's Encrypt.

## 2. Estratégia de Banco de Dados (Hostinger)

Você mencionou a possibilidade de usar o banco da Hostinger para hospedar algumas camadas.

*   **PostgreSQL + PostGIS:** A melhor escolha geoespacial. Como você tem um VPS de 8GB de RAM, você pode subir um container do Postgres com a extensão PostGIS perfeitamente no mesmo servidor.
*   **O que armazenar no banco?**
    1.  **Camadas de Base:** Você pode importar seus arquivos de limites municipais, malha viária pesada ou recortes frequentes diretamente no banco. Em vez de ler GeoParquets ou GeoJSONs grandes via arquivo a cada execução, a API faria *queries* espaciais rápidas (`ST_Intersects`, `ST_ClipByBox2D`) direto no PostGIS.
    2.  **Resultados / Histórico:** As intersecções geradas pelo DuckDB (os relatórios de vias afetadas por nível) podem ser salvas em tabelas do banco em vez de arquivos locais no disco. Isso facilita para o serviço consumidor, que poderia simplesmente ler do banco ou baixar via um endpoint de relatório da API.
*   **DuckDB vs PostGIS:** O seu projeto já usa DuckDB Spatial (que é excelente em memória). Você pode usar o PostGIS como o *armazém* persistente e continuar usando o DuckDB para *analytics* rápido em memória durante a execução do script.

## 3. Gestão de Recursos do Servidor (2 vCPU / 8GB RAM)

Esta é uma máquina excelente, porém o processamento de polígonos exige cuidado.

*   **Memória (8GB):** É suficiente, mas carregar GeoDataFrames do país/estado inteiro na memória vai esgotar rapidamente seus 8GB. Recomendo continuar a estratégia do seu código atual de sempre **recortar (clip) por um Area of Interest (AOI) restrito** antes de realizar os joins e cálculos espaciais pesados.
*   **Processamento (2 vCPU):** Limite o número de *workers* concorrentes se for usar Celery. Com 2 núcleos, configure no máximo 2 ou 3 *workers* pesados em paralelo. Se receberem 10 requisições simultâneas de processamento espaciais, os workers enfileirarão as demais. Isso impede que o servidor trave a ponto de derrubar a própria API ou o Banco de Dados.

## 4. Sugestão de Endpoints (Interface da API)

```python
# Inicia a análise (assíncrono)
POST /api/v1/analyze
Body: {
  "aoi_geojson": { ... },
  "min_level": 1,
  "max_level": 3,
  "network_type": "drive",
  "road_buffer_m": 10.0
}
Response: { "task_id": "abc-123", "status": "processing" }

# Consulta o status / resultados
GET /api/v1/tasks/{task_id}
Response (se finalizado): { 
  "status": "completed", 
  "download_url": "/api/v1/results/abc-123.zip",
  "summary": { "vias_afetadas_nivel_1": 1500 }
}
```

## 5. Próximos Passos Sugeridos (Roadmap de Implementação)

1.  **Refatoração do Código Base:** Isolar as funções do `run.py` para não dependerem de `argparse` ou `print`, retornando dicionários ou pydantic models para a futura API.
2.  **Implementação FastAPI:** Criar um arquivo `api.py` ou pasta `app/` para definir as rotas HTTP que engatilham o processamento.
3.  **Configuração de Banco PostGIS:** Subir a base de dados via Docker e mapear os volumes de dados para não perdê-los se o container for deletado. Otimizar carregamento das camadas (ex: ingestão do raster).
4.  **Criação do Dockerfile e docker-compose.yml:** Empacotar a aplicação Python, as dependências geoespaciais, e orquestrar API + Celery + Redis + Banco PostGIS + Nginx.
5.  **Deploy no VPS Hostinger:** Acessar via SSH, clonar o repositório, configurar domínio (Nginx/Let's Encrypt) e executar `docker-compose up -d`.

> [!TIP]
> **Dica de DevOps:** Como o disco é NVMe (muito rápido!), podemos usar e abusar de operações de leitura de dados tabulares locais (Parquet/GeoParquet), o que casa perfeitamente com a stack do DuckDB.
