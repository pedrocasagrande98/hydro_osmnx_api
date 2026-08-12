"""Pacote hydro_mde: intersecao de manchas de inundacao GLOFAS com vias OSM."""

__version__ = "0.1.0"

from hydro_mde.config import (
    NIVEL_LABELS,
    NIVEL_PALETTE,
    NIVEL_PROFUNDIDADE,
    RASTER_PARQUET,
    EDGES_DEFAULT,
    AOI_BUFFER_DEG,
    CRS_WGS84,
    UTM_SA_ALBERS,
)
from hydro_mde.aoi import build_aoi
from hydro_mde.clip_raster import clip_raster_to_aoi
from hydro_mde.fetch_roads import fetch_roads
from hydro_mde.crossing import find_affected_edges_by_level, find_affected_edges
from hydro_mde.report import write_report_per_level

__all__ = [
    "NIVEL_LABELS",
    "NIVEL_PALETTE",
    "NIVEL_PROFUNDIDADE",
    "RASTER_PARQUET",
    "EDGES_DEFAULT",
    "AOI_BUFFER_DEG",
    "CRS_WGS84",
    "UTM_SA_ALBERS",
    "build_aoi",
    "clip_raster_to_aoi",
    "fetch_roads",
    "find_affected_edges",
    "find_affected_edges_by_level",
    "write_report_per_level",
]