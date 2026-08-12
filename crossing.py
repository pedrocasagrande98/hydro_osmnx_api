"""Cruza vias (edges) com manchas de inundacao (raster clip).

Para cada nivel GLOFAS (1=baixo, 2=medio, 3=critico), retorna um
GeoDataFrame com as vias atingidas, severidade, nivel e comprimento
afetado em metros (projecao ESRI:102033 = South America Albers Equal Area).
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

import duckdb
import geopandas as gpd
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import shape
from shapely import wkb as shapely_wkb
from tqdm import tqdm

from hydro_mde.config import (
    CRS_WGS84,
    NIVEL_LABELS,
    NIVEL_PALETTE,
    UTM_SA_ALBERS,
)


def _ensure_spatial(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL spatial; LOAD spatial;")


def _build_schema(crs_wkt: str):
    from pyproj import CRS
    crs_projjson = None
    try:
        crs_projjson = CRS(crs_wkt).to_json_dict()
    except Exception:
        crs_projjson = None
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "geometry_types": ["MultiLineString", "LineString"],
                "bbox": [float("inf"), float("inf"), float("-inf"), float("-inf")],
            }
        },
    }
    if crs_projjson:
        geo_meta["columns"]["geometry"]["crs"] = crs_projjson
    return pa.schema(
        [
            pa.field("osmid", pa.string(), nullable=True),
            pa.field("highway", pa.string(), nullable=True),
            pa.field("name", pa.string(), nullable=True),
            pa.field("valor_pixel", pa.int32(), nullable=False),
            pa.field("severidade", pa.string(), nullable=False),
            pa.field("comprimento_afetado_m", pa.float64(), nullable=False),
            pa.field("comprimento_total_m", pa.float64(), nullable=False),
            pa.field("fracao_afetada", pa.float64(), nullable=False),
            pa.field("geometry", pa.binary(), nullable=False),
        ],
        metadata={b"geo": json.dumps(geo_meta).encode("utf-8")},
    )


def find_affected_edges(edges_gdf: gpd.GeoDataFrame,
                        raster_gdf: gpd.GeoDataFrame,
                        road_buffer_m: float = 10.0,
                        utm_epsg: str = UTM_SA_ALBERS) -> gpd.GeoDataFrame:
    """Spatial join edges ∩ raster.

    Para cada edge, retorna:
      - ``valor_pixel``: menor (mais severo) nivel que intercepta
      - ``severidade``: slug do nivel
      - ``comprimento_afetado_m``: soma do comprimento das intersecoes (m)
      - ``comprimento_total_m``: comprimento total da via (m)
      - ``fracao_afetada``: comprimento_afetado / comprimento_total

    A geometria de saida eh a geometria original da via (sem buffer).
    O parametro ``road_buffer_m`` alarga a via antes do teste de
    intersecao para evitar perder hits nas bordas.
    """
    if edges_gdf.empty or raster_gdf.empty:
        return gpd.GeoDataFrame(
            columns=[
                "osmid", "highway", "name", "valor_pixel", "severidade",
                "comprimento_afetado_m", "comprimento_total_m",
                "fracao_afetada", "geometry",
            ],
            geometry="geometry",
            crs=CRS_WGS84,
        )

    # DuckDB Spatial nao reconhece ESRI:102033 diretamente. Convertemos para
    # o WKT da projecao (PROJCRS South_America_Albers_Equal_Area_Conic).
    from pyproj import CRS as PyprojCRS
    target_crs = PyprojCRS.from_user_input(utm_epsg)
    target_wkt = target_crs.to_wkt()

    edges = edges_gdf.copy()
    edges["_edge_idx"] = range(len(edges))

    if "osmid" not in edges.columns:
        edges["osmid"] = None
    if "highway" not in edges.columns:
        edges["highway"] = None
    if "name" not in edges.columns:
        edges["name"] = None

    edges["osmid"] = edges["osmid"].apply(
        lambda v: None if v is None else (str(v) if not isinstance(v, (list, tuple)) else ",".join(str(x) for x in v))
    )
    edges["highway"] = edges["highway"].apply(
        lambda v: None if v is None else (str(v) if not isinstance(v, (list, tuple)) else ",".join(str(x) for x in v))
    )
    edges["name"] = edges["name"].apply(
        lambda v: None if v is None else (str(v) if not isinstance(v, (list, tuple)) else ",".join(str(x) for x in v))
    )

    edges_wkt = edges[["_edge_idx", "osmid", "highway", "name", "geometry"]].copy()
    edges_wkt["geometry_wkt"] = edges_wkt.geometry.apply(lambda g: g.wkt)
    edges_wkt = edges_wkt.drop(columns=["geometry"])

    raster = raster_gdf.copy()
    raster["_raster_idx"] = range(len(raster))
    raster["geometry_wkt"] = raster.geometry.apply(lambda g: g.wkt)
    raster_input = raster[["_raster_idx", "valor_pixel", "geometry_wkt"]]

    con = duckdb.connect()
    _ensure_spatial(con)

    # Salva tabelas temporarias em parquet (DuckDB Spatial aceita geometria como WKT)
    edges_input_path = "_tmp_edges.parquet"
    raster_input_path = "_tmp_raster.parquet"
    edges_wkt[["_edge_idx", "osmid", "highway", "name", "geometry_wkt"]].to_parquet(
        edges_input_path, index=False
    )
    raster_input.to_parquet(raster_input_path, index=False)

    # Cruza: para cada edge, encontra o menor valor_pixel que intercepta
    # (mais severo). Para cada par (edge, raster), calcula o comprimento da
    # intersecao em metros via ST_Transform -> UTM.
    sql = f"""
        WITH cr AS (
          SELECT
            e._edge_idx AS edge_idx,
            e.osmid     AS osmid,
            e.highway   AS highway,
            e.name      AS name,
            r.valor_pixel AS valor_pixel,
            ST_Length(
              ST_Transform(
                ST_Intersection(
                  ST_SetCRS(ST_GeomFromText(e.geometry_wkt), 'EPSG:4326'),
                  ST_SetCRS(ST_GeomFromText(r.geometry_wkt), 'EPSG:4326')
                ),
                '{target_wkt}'
              )
            ) AS comp_m
          FROM read_parquet('{edges_input_path}') e
          JOIN read_parquet('{raster_input_path}') r
            ON ST_Intersects(
                 ST_Buffer(ST_SetCRS(ST_GeomFromText(e.geometry_wkt), 'EPSG:4326'), 0.0001),
                 ST_SetCRS(ST_GeomFromText(r.geometry_wkt), 'EPSG:4326')
               )
        ),
        agg AS (
          SELECT
            edge_idx,
            MIN(valor_pixel) AS valor_pixel,
            SUM(comp_m)     AS comprimento_afetado_m
          FROM cr
          WHERE comp_m > 0
          GROUP BY edge_idx
        )
        SELECT
          e._edge_idx    AS edge_idx,
          e.osmid        AS osmid,
          e.highway      AS highway,
          e.name         AS name,
          a.valor_pixel  AS valor_pixel,
          a.comprimento_afetado_m AS comprimento_afetado_m,
          ST_Length(
            ST_Transform(ST_SetCRS(ST_GeomFromText(e.geometry_wkt), 'EPSG:4326'), '{target_wkt}')
          ) AS comprimento_total_m
        FROM read_parquet('{edges_input_path}') e
        JOIN agg a ON e._edge_idx = a.edge_idx
    """
    result = con.execute(sql).df()

    os.remove(edges_input_path)
    os.remove(raster_input_path)

    if result.empty:
        return gpd.GeoDataFrame(
            columns=[
                "osmid", "highway", "name", "valor_pixel", "severidade",
                "comprimento_afetado_m", "comprimento_total_m",
                "fracao_afetada", "geometry",
            ],
            geometry="geometry",
            crs=CRS_WGS84,
        )

    result["severidade"] = result["valor_pixel"].map(
        {n: slug for n, (slug, _) in NIVEL_LABELS.items()}
    )
    result["fracao_afetada"] = (
        result["comprimento_afetado_m"] / result["comprimento_total_m"]
    ).clip(upper=1.0)

    edges_indexed = edges.set_index("_edge_idx")
    result["geometry"] = result["edge_idx"].map(edges_indexed["geometry"])
    result = gpd.GeoDataFrame(result, geometry="geometry", crs=CRS_WGS84)
    result = result.drop(columns=["edge_idx"])
    result = result.sort_values(["valor_pixel", "comprimento_afetado_m"],
                                 ascending=[True, False]).reset_index(drop=True)

    return result


def find_affected_edges_by_level(edges_gdf: gpd.GeoDataFrame,
                                 raster_gdf: gpd.GeoDataFrame,
                                 road_buffer_m: float = 10.0,
                                 utm_epsg: str = UTM_SA_ALBERS,
                                 ) -> Dict[int, gpd.GeoDataFrame]:
    """Aplica ``find_affected_edges`` filtrando o raster por nivel.

    Retorna dicionario ``{nivel: GeoDataFrame}`` com 3 chaves (1, 2, 3).
    """
    result: Dict[int, gpd.GeoDataFrame] = {}
    for nivel in (1, 2, 3):
        sub = raster_gdf[raster_gdf["valor_pixel"] == nivel]
        affected = find_affected_edges(
            edges_gdf, sub, road_buffer_m=road_buffer_m, utm_epsg=utm_epsg,
        )
        result[nivel] = affected
    return result


def write_affected_parquet(gdf: gpd.GeoDataFrame,
                           output_path: str,
                           crs: str = CRS_WGS84,
                           show_progress: bool = True) -> None:
    """Persiste um GeoDataFrame de vias afetadas em GeoParquet 1.1.0."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    from pyproj import CRS as PyprojCRS
    crs_wkt = PyprojCRS.from_user_input(crs).to_wkt()
    schema = _build_schema(crs_wkt)

    with pq.ParquetWriter(output_path, schema, compression="snappy") as w:
        buffer = []
        iterator = tqdm(
            gdf.itertuples(index=False),
            total=len(gdf),
            desc=f"Gravando {os.path.basename(output_path)}",
            disable=not show_progress,
        ) if not gdf.empty else []
        for row in iterator:
            buffer.append({
                "osmid": str(row.osmid) if row.osmid is not None else None,
                "highway": str(row.highway) if row.highway is not None else None,
                "name": str(row.name) if row.name is not None else None,
                "valor_pixel": int(row.valor_pixel),
                "severidade": str(row.severidade),
                "comprimento_afetado_m": float(row.comprimento_afetado_m),
                "comprimento_total_m": float(row.comprimento_total_m),
                "fracao_afetada": float(row.fracao_afetada),
                "geometry": row.geometry.wkb,
            })
            if len(buffer) >= 10_000:
                _flush(buffer, schema, w)
                buffer.clear()
        if buffer:
            _flush(buffer, schema, w)
            buffer.clear()


def _flush(buffer, schema, writer):
    if not buffer:
        return
    table = pa.Table.from_pydict({
        "osmid": [r["osmid"] for r in buffer],
        "highway": [r["highway"] for r in buffer],
        "name": [r["name"] for r in buffer],
        "valor_pixel": [r["valor_pixel"] for r in buffer],
        "severidade": [r["severidade"] for r in buffer],
        "comprimento_afetado_m": [r["comprimento_afetado_m"] for r in buffer],
        "comprimento_total_m": [r["comprimento_total_m"] for r in buffer],
        "fracao_afetada": [r["fracao_afetada"] for r in buffer],
        "geometry": [r["geometry"] for r in buffer],
    }, schema=schema)
    writer.write_table(table)