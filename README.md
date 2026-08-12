# hydro_mde_API

> Identificação de vias afetadas por uma possível inundação em uma cidade,
> cruzando manchas de **inundação GLOFAS** com a **malha viária do
> OpenStreetMap**, recortada a uma Área de Interesse (AOI) configurável.

---

## 🎯 Objetivo do projeto

**Realizar uma identificação das vias afetadas por uma possível inundação
na cidade**, cruzando dois insumos:

1. **Manchas de inundação GLOFAS** — raster do *Global Flood Awareness
   System* (Copernicus EMS) reclassificado em **três níveis de risco** de
   acordo com a profundidade estimada para um **período de retorno de
   100 anos**.
2. **Malha viária** do OpenStreetMap, obtida via **OSMnx** (online) ou a
   partir de um arquivo `edges.geojson` local (modo `--offline`),
   recortada a uma **Área de Interesse (AOI)** arbitrária.

O pipeline entrega, para cada nível de risco, uma camada **GeoJSON** com
as vias atingidas, o **comprimento afetado em metros** e a **fração
comprometida da via** — pronta para uso em QGIS, Google Earth Engine,
APIs de roteamento ou painéis de defesa civil.

### Por que isso importa

- **Defesa civil e prefeituras**: priorização de interdições, simulação
  de rotas alternativas, planos de contingência.
- **Planejamento urbano**: identificação de gargalos viários em zonas de
  risco recorrente.
- **Operadoras de logística**: avaliação de impacto operacional em
  eventos extremos.
- **Comunicação de risco**: mapas rápidos (1 camada por nível) que
  traduzem um raster científico em informação acionável.

### Casos de uso típicos

- "Quais ruas de uma cidade ficam intransitáveis em uma cheia de 100
  anos?"
- "Qual o comprimento total de via afetada por nível de risco?"
- "Onde estão os pontos críticos que combinam **risco alto + vias
  arteriais**?"
- "Quanto da malha viária municipal ficaria comprometida em um evento
  extremo?"

### Saídas esperadas

| Para o stakeholder | Onde encontrar |
|---|---|
| Mapa das vias atingidas por nível de risco | `outputs/vias_afetadas_nivel_*.geojson` |
| Tabela resumo (CSV) com métricas por nível | `outputs/relatorio.csv` |
| Tabela resumo em JSON (machine-readable) | `outputs/relatorio.json` |
| AOI efetivamente usado no recorte | `outputs/aoi.geojson` |
| Vias OSM recortadas à AOI | `outputs/edges_aoi.geojson` |
| Manchas GLOFAS recortadas à AOI | `outputs/raster_clip.parquet` |

---

## 👥 Visão geral (para stakeholders)

### O que entra

- Um **raster GLOFAS** já reclassificado em 3 classes (1, 2, 3).
- Uma **AOI** (polígono em GeoJSON/Shapefile) **ou** a malha viária da
  cidade (o pipeline deriva a AOI do bbox das vias, expandido em
  ~500 m).
- Acesso à internet para baixar vias OSM **ou** um `edges.geojson`
  local.

### O que sai

- 3 arquivos GeoJSON (um por nível de risco) com as vias atingidas.
- 1 relatório em CSV e 1 em JSON com o total de vias afetadas, o
  comprimento total afetado e o percentual da malha viária
  comprometido por nível.
- 1 camada de manchas GLOFAS recortada exatamente à AOI.

### Tempo típico

Para uma cidade de ~300 km² com ~3.000 vias e algumas centenas de
manchas: **< 10 segundos** em um laptop comum (modo `--offline`).

### Limitações atuais (resumo)

- Vias sobre **pontes** ainda contam como afetadas (a máscara de
  hidrografia natural ainda é TODO).
- A AOI recebe um **buffer padrão de 0.005° (~500 m)** para garantir
  que manchas de borda não sejam perdidas — configurável.
- O raster de entrada precisa estar **pré-reclassificado em 3 classes**
  no Earth Engine (vide `Glofas.js`).

---

## 🛠️ Guia técnico (para devs / analistas GIS)

### Pré-requisitos

- Python ≥ 3.11
- [`uv`](https://docs.astral.sh/uv/) para gestão de dependências
- Raster GLOFAS do Brasil reclassificado (`saida_rasterio.parquet`,
  gerado pelos scripts `raster2vector_*.py` da raiz do repositório)
- (Opcional) Conta de acesso ao **OpenStreetMap** via OSMnx

### Instalação

```bash
# Ambiente base (rasterio, geopandas, shapely, duckdb, pyarrow, tqdm)
uv sync

# Extras opcionais
uv sync --extra osmnx     # adiciona osmnx, matplotlib, ipykernel
uv sync --extra notebook  # adiciona jupyterlab
```

### Como funciona (pipeline em 4 etapas)

```
┌─────────────────────┐
│ 1) build_aoi()      │  → outputs/aoi.geojson
│   (AOI do bbox das  │
│    vias + buffer)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2) clip_raster_to_  │  → outputs/raster_clip.parquet
│    aoi()            │    (DuckDB Spatial + ST_Intersection,
│   (recorte REAL do  │     bbox exatamente = AOI)
│    raster à AOI)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3) fetch_roads()    │  → outputs/edges_aoi.geojson
│   (OSMnx online ou  │
│    edges.geojson    │
│    local offline)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ 4) find_affected_edges_by_level()       │
│   (DuckDB Spatial: vias x manchas,      │
│    buffer de 10 m nas vias, agrega      │
│    por nível GLOFAS)                    │
└──────────┬──────────────────────────────┘
           │
           ▼
   outputs/vias_afetadas_nivel_*.geojson
   outputs/relatorio.csv
   outputs/relatorio.json
```

### Uso rápido (CLI)

```bash
# Modo offline (reusa edges.geojson local — rápido)
python -m hydro_mde_API --offline

# Modo online (baixa vias via OSMnx)
uv sync --extra osmnx
python -m hydro_mde_API --network-type drive

# AOI custom (qualquer geojson/shapefile)
python -m hydro_mde_API --offline \
    --aoi-file minha_aoi.geojson \
    --output-dir resultados/

# Apenas níveis médio + crítico, buffer de 15 m nas vias
python -m hydro_mde_API --offline \
    --min-level 2 --max-level 3 \
    --road-buffer-m 15
```

### Argumentos CLI

| Flag | Default | Descrição |
|---|---|---|
| `--edges` | `../edges.geojson` | Vias de entrada (origem da AOI) |
| `--aoi-file` | _(vazio)_ | Geometria arbitrária que sobrescreve o bbox de edges |
| `--buffer-deg` | `0.005` | Folga no AOI em graus (~500 m) |
| `--raster` | `../saida_rasterio.parquet` | GeoParquet GLOFAS |
| `--min-level` | `1` | Nível GLOFAS mínimo (1, 2 ou 3) |
| `--max-level` | `3` | Nível GLOFAS máximo (1, 2 ou 3) |
| `--network-type` | `drive` | Tipo de rede OSMnx: `drive`, `drive_service`, `walk`, `bike`, `all` |
| `--road-buffer-m` | `10.0` | Buffer aplicado às vias antes do join (metros) |
| `--utm-epsg` | `ESRI:102033` | Projeção métrica para cálculo de comprimento |
| `--offline` | `false` | Reusa `edges.geojson` em vez de baixar via OSMnx |
| `--output-dir` | `hydro_mde_API/outputs/` | Pasta de saída |

### Saídas geradas

| Arquivo | Conteúdo |
|---|---|
| `aoi.geojson` | AOI final usado (Feature Polygon em EPSG:4326) |
| `raster_clip.parquet` | Manchas GLOFAS recortadas **exatamente** à AOI (GeoParquet 1.1.0) |
| `edges_aoi.geojson` | Vias OSM recortadas à AOI |
| `vias_afetadas_nivel_1_baixo_risco.geojson` | Vias atingidas (baixo risco) |
| `vias_afetadas_nivel_2_medio_risco.geojson` | Vias atingidas (médio risco) |
| `vias_afetadas_nivel_3_risco_critico.geojson` | Vias atingidas (risco crítico) |
| `relatorio.csv` | Tabela sumário por nível |
| `relatorio.json` | Métricas em JSON (machine-readable) |

### Legenda GLOFAS (`valor_pixel`)

Definida em [`../Glofas.js`](../Glofas.js):

| `valor_pixel` | Severidade | Profundidade |
|---|---|---|
| 1 | `baixo_risco`   | 0 m < profundidade ≤ 1 m |
| 2 | `medio_risco`   | 1 m < profundidade ≤ 3 m |
| 3 | `risco_critico` | profundidade > 3 m |

> O raster já vem com máscara `depth > 0` aplicada no Earth Engine,
> então `valor_pixel = 0` (áreas secas) **não** aparece no GeoParquet de
> saída.

### Colunas dos GeoJSON de saída

Cada `vias_afetadas_nivel_*` carrega:

| Coluna | Tipo | Descrição |
|---|---|---|
| `osmid` | str | ID OSM da via |
| `highway` | str | Tipo da via (`residential`, `primary`, …) |
| `name` | str | Nome (se houver) |
| `valor_pixel` | int | Nível GLOFAS que afeta esta via |
| `severidade` | str | `baixo_risco` / `medio_risco` / `risco_critico` |
| `comprimento_afetado_m` | float | Soma do comprimento das interseções (m, em ESRI:102033) |
| `comprimento_total_m` | float | Comprimento total da via (m) |
| `fracao_afetada` | float | `comprimento_afetado_m / comprimento_total_m` (0–1) |
| `geometry` | LineString | Geometria original da via |

### API Python (uso programático)

```python
from hydro_mde_API import (
    build_aoi,
    clip_raster_to_aoi,
    fetch_roads,
    find_affected_edges_by_level,
    write_report_per_level,
)

aoi = build_aoi(
    edges_path="../edges.geojson",
    aoi_file=None,            # ou "minha_aoi.geojson"
    buffer_deg=0.005,
    output_path="outputs/aoi.geojson",
)

raster_gdf = clip_raster_to_aoi(
    aoi,
    raster_path="../saida_rasterio.parquet",
    min_level=1, max_level=3,
    output_path="outputs/raster_clip.parquet",
)

edges_gdf = fetch_roads(
    aoi,
    network_type="drive",
    offline=True,
    edges_path="../edges.geojson",
    output_path="outputs/edges_aoi.geojson",
)

by_level = find_affected_edges_by_level(
    edges_gdf, raster_gdf,
    road_buffer_m=10.0,
    utm_epsg="ESRI:102033",
)

paths = write_report_per_level(
    by_level,
    edges_total=len(edges_gdf),
    edges_total_length_m=...,
    output_dir="outputs/",
)
```

### Performance & otimizações

- **Recorte real com `ST_Intersection`** (não `ST_Intersects`): o
  `raster_clip.parquet` é limitado geometricamente à AOI, **sem**
  extrapolação de polígonos. Validação: 100% dos polígonos passam em
  `ST_Within(AOI)`.
- **Filtro `ST_Intersects` no `WHERE`**: garante que o
  `ST_Intersection` (mais caro) só rode nos candidatos que tocam a
  AOI — em vez das 3,9 M linhas do raster Brasil.
- **Filtro `NOT ST_IsEmpty`**: descarta geometrias degeneradas
  (polígonos tangentes que viram linha/ponto).
- **ProcessPool** no `raster2vector_rasterio_e_geopandas.py` com
  `cpu_count()` workers e janelas 2048×2048 autodetectadas.
- **`ParquetWriter` chunked** a cada 10 k features.
- **GeoParquet 1.1.0** com CRS em PROJJSON (compatível com QGIS,
  GeoPandas, DuckDB).
- **Cálculo de comprimento** em projeção equal-area
  (`ESRI:102033` — South America Albers).

### Projeções

- **Entrada/saída vetorial**: `EPSG:4326` (WGS84)
- **Cálculo de comprimento**: `ESRI:102033` (South America Albers
  Equal Area, em metros)

### Limitações e TODOs

- **`fetch_waterways.py`**: baixar hidrografia OSM (`natural=water`,
  `waterway=*`) para usar como **máscara de exclusão** — vias sobre
  pontes não deveriam contar como afetadas.
- **`AOI_BUFFER_DEG = 0.005`** (~500 m): preservado por padrão para não
  perder manchas de borda; ajustar para `0.0` quando a AOI já é a área
  exata de interesse.
- **Dependência online do OSMnx** quando `--offline` não é passado.
- O raster de entrada precisa estar **pré-reclassificado em 3 classes**
  no Earth Engine (vide `Glofas.js`).

### Estrutura do pacote

```
hydro_mde_API/
├── __init__.py            # API pública do pacote
├── __main__.py            # entrypoint `python -m hydro_mde_API`
├── config.py              # constantes + legenda
├── aoi.py                 # build_aoi()
├── clip_raster.py         # clip_raster_to_aoi() via DuckDB Spatial
├── fetch_roads.py         # fetch_roads() (OSMnx online / offline)
├── fetch_waterways.py     # TODO (hidrografia natural)
├── crossing.py            # find_affected_edges_by_level()
├── report.py              # write_report_per_level()
├── run.py                 # CLI argparse
├── README.md              # este arquivo
└── outputs/               # (gitignored) artefatos
```

---

## 📚 Referências

- **GLOFAS** — *Global Flood Awareness System*,
  [Copernicus Emergency Management Service](https://globalfloods.eu/).
- **OpenStreetMap** — [openstreetmap.org](https://www.openstreetmap.org/),
  via [OSMnx](https://osmnx.readthedocs.io/) (Boeing, 2017).
- **DuckDB Spatial** — extensão espacial do
  [DuckDB](https://duckdb.org/), com `ST_Intersection`,
  `ST_Intersects`, `ST_Within`, etc.
- **GeoParquet 1.1.0** —
  [geoparquet.org](https://geoparquet.org/) (encoding WKB + CRS em
  PROJJSON).