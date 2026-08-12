# Guia Definitivo de Deploy na Hostinger VPS (Atualizado)

Este documento registra todo o histórico de desafios superados e estabelece o guia oficial e definitivo para subir a infraestrutura da `hydro_osmnx_api` no servidor Hostinger VPS.

## 1. Arquitetura da Solução
A aplicação roda sob uma arquitetura de microsserviços conteinerizada:
- **Proxy (Nginx)**: Roda na porta `80` externa, roteando tráfego para a API.
- **API (FastAPI/Uvicorn)**: Roda na porta interna `8000` (mapeada para `8001` externamente para evitar conflitos com o Cyberpanel).
- **Broker (Redis)**: Roda internamente (porta fechada para a web) gerenciando a fila de processamento.
- **Worker (Celery)**: Processa as análises geoespaciais assíncronas em background.

## 2. Histórico de Bugs Resolvidos
Durante o deploy inicial, enfrentamos e solucionamos os seguintes gargalos:

- **Conflito de Porta**: A porta `8000` já estava em uso pelo painel da Hostinger (Cyberpanel). **Solução:** O `docker-compose.yml` foi alterado para mapear a API para `8001:8000`.
- **Certbot bloqueando Deploy**: O contêiner do certbot saía imediatamente (`Exit 0`), o que derrubava o deploy no painel da Hostinger. **Solução:** O serviço do certbot foi temporariamente comentado até a configuração de domínio oficial (SSL).
- **Upload de Arquivo Gigante**: O SCP (`ssh`) bloqueou o envio do arquivo `saida_rasterio.parquet` de 291MB (`Permission Denied`). **Solução:** Usamos o próprio contêiner da API para baixar do Google Drive via `gdown`.
- **Payload Ignorado**: O Pydantic (FastAPI) estava cortando as variáveis do GeoJSON (`raster`, `edges`) pois não estavam tipadas no `AnalyzeRequest`. **Solução:** Adicionado tipagem explícita no endpoint e correção da lógica em `geospatial.py` para salvar o GeoJSON recebido.

## 3. Passo a Passo do Deploy Limpo

### A. Clonar/Atualizar e Subir os Contêineres
Acesse o terminal SSH da VPS e execute:
```bash
cd ~/hydro_osmnx_api
git pull
docker compose down
docker compose up -d --build
```
> **Nota:** Todos os arquivos gerados (entradas e saídas de processamento) e o banco de dados temporário persistem graças ao mapeamento `volumes: - .:/app` no Docker Compose.

### B. Injetando Dados Pesados (Raster Parquet)
Como o envio de arquivos >200MB via painel ou SSH pode falhar, suba o arquivo para o Google Drive, obtenha o link de compartilhamento público e baixe-o de dentro do contêiner da API:
```bash
docker exec -it hydro_osmnx_api-api-1 bash -c "pip install gdown && gdown ID_DO_ARQUIVO_NO_DRIVE -O /app/data/saida_rasterio.parquet"
```
Isso garante que o arquivo seja salvo diretamente no host da VPS em `~/hydro_osmnx_api/data/saida_rasterio.parquet`.

## 4. O Fluxo de Funcionamento (Entendendo o Motor)
1. **POST**: O usuário envia um GeoJSON em `/api/v1/analyze`.
2. **Fila**: A API retorna um `task_id` imediatamente e empurra o GeoJSON pro Redis.
3. **Worker**: O Celery pega a task, recorta o GeoParquet gigante usando o GeoJSON recebido, cruza com vias do OpenStreetMap (OSMnx) e gera um ZIP em `data/outputs/{task_id}/resultados.zip`.
4. **Polling/Download**: O usuário continua consultando `GET /api/v1/tasks/{task_id}` até dar `completed`, momento em que acessa `GET /api/v1/download/{task_id}` para baixar o ZIP final. O arquivo gerado permanece armazenado na VPS.
