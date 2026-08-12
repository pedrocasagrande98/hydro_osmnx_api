# Guia de Deploy e Teste na Hostinger VPS

Este documento serve como um guia (handover) para o próximo agente ou desenvolvedor que for configurar e testar a aplicação `hydro_osmnx_api` no servidor Hostinger VPS.

## 1. Estrutura do Servidor (Revisão)
- **Máquina:** 2 vCPU, 8 GB RAM, 100 GB NVMe.
- **Stack:** Docker, Docker Compose, Nginx, Redis, Celery, FastAPI.
- **Projeto Base:** `hydro_osmnx_api/`

## 2. Pré-requisitos na VPS
Antes de iniciar o projeto, certifique-se de que os seguintes componentes estão instalados na Hostinger:
- **Docker e Docker Compose**
- **Portas Abertas no Firewall:** `80` (HTTP), `443` (HTTPS) e `22` (SSH).

## 3. Gestão de Dados (Camadas Geoespaciais)
A API necessita de arquivos estáticos pesados para realizar o geoprocessamento em background (Celery Worker). 
**Passo crucial:** Crie uma pasta `data/` dentro da raiz do projeto (`hydro_osmnx_api/data/`) e faça o upload dos seguintes arquivos para o servidor:
- `saida_rasterio.parquet` (O arquivo GeoParquet do GLOFAS).
- `edges.geojson` (Opcional, se a requisição usar malha pré-calculada).

> **Atenção Próximo Agente:** É imperativo mapear o volume local de dados no `docker-compose.yml`. Certifique-se de que os serviços `api` e `celery_worker` tenham o volume `- ./data:/app/data` configurado no yaml antes do deploy.

## 4. Subindo a Aplicação
No terminal do servidor Hostinger, navegue até a pasta do projeto:

```bash
# 1. Ajuste as variáveis de ambiente
cp .env.example .env

# 2. Build da imagem (Isso pode demorar alguns minutos na primeira vez por conta do GDAL)
docker-compose build

# 3. Inicie os contêineres
docker-compose up -d
```

## 5. Como Testar e Validar
Para confirmar que o ambiente subiu corretamente:
1. **Logs:** 
   `docker-compose logs -f celery_worker` (garanta que ele conectou no Redis).
2. **Saúde da API:** 
   Acesse via navegador `http://<IP_DA_HOSTINGER>/docs` (se a porta 8000 estiver exposta) ou a rota raiz que você configurar no Nginx.
3. **Teste Funcional:** 
   Dispare uma requisição via `POST` na rota `/api/v1/analyze` com um GeoJSON de teste pequeno. O Celery deve imprimir "Iniciando processamento" no log e aguardar os 5 segundos do mock atual.

## 6. Próximos Passos de Desenvolvimento (Para o próximo agente)
1. Concluir a refatoração do código do `run.py` original movendo a lógica geoespacial (`DuckDB`, `GeoPandas`) para `app/services/geospatial.py`.
2. Incluir a rotina de mapeamento de output para devolver o link ou o buffer ZIPado do GeoJSON gerado pela análise.
3. Configurar Certbot no Nginx (`nginx.conf`) para encriptação SSL (HTTPS).
