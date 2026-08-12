"""TODO: download de hidrografia OSM (rios, lagos) para mascara de exclusao.

Sera implementado proxima entrega para distinguir:
  - Inundacao GLOFAS (mancha prevista, nao necessariamente agua permanente)
  - Corpos d'agua permanentes (rivers, lakes) que NAO devem contar como
    "via afetada" — a via ja esta sobre uma ponte, por exemplo.

API prevista:
  fetch_waterways(aoi: Polygon, output_path: str) -> gpd.GeoDataFrame
"""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Polygon


def fetch_waterways(aoi: Polygon, output_path: str) -> gpd.GeoDataFrame:
    """TODO: ainda nao implementado."""
    raise NotImplementedError(
        "fetch_waterways() sera implementado na proxima entrega. "
        "Tags OSM previstas: {'natural': 'water'} e {'waterway': True}."
    )