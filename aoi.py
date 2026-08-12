"""Construcao da Area de Interesse (AOI) a partir de geometria de entrada."""

from __future__ import annotations

import json
import os
from typing import Optional

import geopandas as gpd
from shapely.geometry import Polygon, mapping


def _bbox_to_polygon(minx: float, miny: float, maxx: float, maxy: float,
                     buffer_deg: float) -> Polygon:
    """Constroi retangulo expandido a partir de bbox lon/lat."""
    return Polygon([
        (minx - buffer_deg, miny - buffer_deg),
        (maxx + buffer_deg, miny - buffer_deg),
        (maxx + buffer_deg, maxy + buffer_deg),
        (minx - buffer_deg, maxy + buffer_deg),
        (minx - buffer_deg, miny - buffer_deg),
    ])


def build_aoi(edges_path: Optional[str] = None,
              aoi_file: Optional[str] = None,
              buffer_deg: float = 0.005,
              output_path: Optional[str] = None) -> Polygon:
    """Constroi o AOI.

    Prioridade:
      1. ``aoi_file`` : geometria/feature-collection arbitrario (.geojson, .gpkg, .shp)
      2. ``edges_path`` : bbox das vias + buffer
      3. Padrao : ``hydro_mde.config.EDGES_DEFAULT``

    Retorna Shapely ``Polygon`` em EPSG:4326 (lon/lat).
    """
    if aoi_file:
        if not os.path.exists(aoi_file):
            raise FileNotFoundError(f"AOI file nao encontrado: {aoi_file}")
        gdf = gpd.read_file(aoi_file)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif str(gdf.crs).upper() not in ("EPSG:4326", "WGS84", "OGC:CRS84"):
            gdf = gdf.to_crs("EPSG:4326")
        aoi = gdf.geometry.union_all()
        aoi = aoi.buffer(buffer_deg)
    else:
        path = edges_path or _default_edges_path()
        if not os.path.exists(path):
            raise FileNotFoundError(f"Edges nao encontrado: {path}")
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif str(gdf.crs).upper() not in ("EPSG:4326", "WGS84", "OGC:CRS84"):
            gdf = gdf.to_crs("EPSG:4326")
        bounds = gdf.total_bounds
        aoi = _bbox_to_polygon(*bounds, buffer_deg=buffer_deg)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fp:
            json.dump(
                {"type": "Feature", "geometry": mapping(aoi),
                 "properties": {"crs": "EPSG:4326"}},
                fp,
                ensure_ascii=False,
            )

    return aoi


def _default_edges_path() -> str:
    from hydro_mde.config import EDGES_DEFAULT
    return EDGES_DEFAULT