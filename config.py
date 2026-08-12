"""Constantes centralizadas do hydro_mde.

Legenda oficial das classes GLOFAS (vide Glofas.js):
  1 = Baixo Risco    : 0m < profundidade <= 1m
  2 = Medio Risco    : 1m < profundidade <= 3m
  3 = Risco Critico  : profundidade > 3m
"""

from __future__ import annotations

import os

RASTER_PARQUET = os.environ.get(
    "HYDRO_RASTER_PARQUET",
    os.path.join(os.path.dirname(__file__), "..", "saida_rasterio.parquet"),
)
EDGES_DEFAULT = os.environ.get(
    "HYDRO_EDGES_DEFAULT",
    os.path.join(os.path.dirname(__file__), "..", "edges.geojson"),
)
AOI_BUFFER_DEG = float(os.environ.get("HYDRO_AOI_BUFFER_DEG", "0.005"))

CRS_WGS84 = "EPSG:4326"

# Projecao equal-area usada para calculo de comprimento em metros.
# ESRI:102033 = South America Albers Equal Area (metros).
UTM_SA_ALBERS = "ESRI:102033"

# Paleta oficial GLOFAS (vide Glofas.js, visParams)
NIVEL_PALETTE = {
    1: "#f1eef6",
    2: "#74a9cf",
    3: "#0570b0",
}

# Legenda dos niveis (slug + descricao humana)
NIVEL_LABELS = {
    1: ("baixo_risco",   "0m < profundidade <= 1m"),
    2: ("medio_risco",   "1m < profundidade <= 3m"),
    3: ("risco_critico", "profundidade > 3m"),
}

NIVEL_PROFUNDIDADE = {n: desc for n, (_, desc) in NIVEL_LABELS.items()}

WORKERS = max(1, os.cpu_count() or 4)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")