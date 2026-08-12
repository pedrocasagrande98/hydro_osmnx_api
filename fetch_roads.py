"""Download ou reuso de vias OSM dentro do AOI."""

from __future__ import annotations

import json
import os
from typing import Optional

import geopandas as gpd
from shapely.geometry import Polygon
from tqdm import tqdm

from hydro_mde.config import CRS_WGS84, EDGES_DEFAULT


def fetch_roads(aoi: Polygon,
                network_type: str = "drive",
                offline: bool = False,
                edges_path: Optional[str] = None,
                output_path: Optional[str] = None,
                show_progress: bool = True) -> gpd.GeoDataFrame:
    """Obtem vias dentro do AOI.

    - ``offline=True`` : reusa ``edges_path`` (default ``edges.geojson``),
                        clipando ao AOI para consistencia.
    - ``offline=False``: baixa via ``osmnx.graph_from_polygon`` (requer
                        o extra ``osmnx`` instalado).
    """
    if offline:
        path = edges_path or EDGES_DEFAULT
        if not os.path.exists(path):
            raise FileNotFoundError(f"Edges nao encontrado: {path}")
        if show_progress:
            print(f"Modo offline: lendo {path}")
        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        elif str(gdf.crs).upper() not in ("EPSG:4326", "WGS84", "OGC:CRS84"):
            gdf = gdf.to_crs("EPSG:4326")

        aoi_gdf = gpd.GeoDataFrame(geometry=[aoi], crs="EPSG:4326")
        if show_progress:
            print(f"  edges lidos: {len(gdf):,} | clipando ao AOI...")
        gdf = gpd.clip(gdf, aoi_gdf)
    else:
        try:
            import osmnx as ox
        except ImportError as e:
            raise ImportError(
                "Modo online requer o extra 'osmnx'. "
                "Instale com: uv sync --extra osmnx"
            ) from e
        if show_progress:
            print(f"Modo online: baixando vias via OSMnx ({network_type})...")
        tqdm.write("  chamando ox.graph_from_polygon (pode levar ~30s)")
        G = ox.graph_from_polygon(aoi, network_type=network_type)
        edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
        gdf = edges.reset_index().rename(columns={"u": "node_u", "v": "node_v"})

    if gdf.empty:
        if show_progress:
            print("  nenhuma via encontrada dentro do AOI")

    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_WGS84)
    else:
        gdf = gdf.to_crs(CRS_WGS84)

    if show_progress:
        print(f"  vias no AOI: {len(gdf):,}")

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        if str(output_path).lower().endswith(".geojson"):
            gdf.to_file(output_path, driver="GeoJSON")
        else:
            gdf.to_file(output_path)

    return gdf