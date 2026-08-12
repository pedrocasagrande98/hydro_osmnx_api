"""Clip do raster GLOFAS (GeoParquet) ao AOI via DuckDB Spatial."""

from __future__ import annotations

import os
from typing import Optional

import duckdb
import geopandas as gpd
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import Polygon, mapping
from tqdm import tqdm

from hydro_mde.config import RASTER_PARQUET, CRS_WGS84
from shapely import wkb as shapely_wkb


def _ensure_spatial(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL spatial; LOAD spatial;")


def _schema_with_crs(crs_wkt: str):
    import json
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
                "geometry_types": ["Polygon", "MultiPolygon"],
                "bbox": [float("inf"), float("inf"), float("-inf"), float("-inf")],
            }
        },
    }
    if crs_projjson:
        geo_meta["columns"]["geometry"]["crs"] = crs_projjson
    return pa.schema(
        [
            pa.field("valor_pixel", pa.int32(), nullable=False),
            pa.field("geometry", pa.binary(), nullable=False),
        ],
        metadata={b"geo": json.dumps(geo_meta).encode("utf-8")},
    )


def clip_raster_to_aoi(aoi: Polygon,
                       raster_path: str = RASTER_PARQUET,
                       min_level: int = 1,
                       max_level: int = 3,
                       output_path: Optional[str] = None,
                       show_progress: bool = True) -> gpd.GeoDataFrame:
    """Clip colunar do raster ao AOI via DuckDB Spatial.

    Retorna GeoDataFrame com colunas ``valor_pixel`` e ``geometry``.
    Se ``output_path`` for definido, persiste em GeoParquet 1.1.0 com CRS.
    """
    if not os.path.exists(raster_path):
        raise FileNotFoundError(f"Raster nao encontrado: {raster_path}")

    con = duckdb.connect()
    _ensure_spatial(con)

    aoi_wkt = aoi.wkt

    df = con.execute(
        f"""
        WITH clip AS (
          SELECT
            valor_pixel,
            ST_Intersection(
              ST_SetCRS(ST_GeomFromWKB(geometry), 'EPSG:4326'),
              ST_SetCRS(ST_GeomFromText('{aoi_wkt}'), 'EPSG:4326')
            ) AS geometry
          FROM read_parquet('{raster_path}')
          WHERE valor_pixel BETWEEN {min_level} AND {max_level}
            AND ST_Intersects(
                  ST_SetCRS(ST_GeomFromWKB(geometry), 'EPSG:4326'),
                  ST_SetCRS(ST_GeomFromText('{aoi_wkt}'), 'EPSG:4326')
                )
        )
        SELECT valor_pixel, geometry FROM clip
        WHERE NOT ST_IsEmpty(geometry)
        """
    ).df()

    if show_progress:
        print(f"Clip raster: {len(df):,} poligonos dentro do AOI")

    if df.empty:
        gdf = gpd.GeoDataFrame(
            {"valor_pixel": [], "geometry": []},
            geometry="geometry",
            crs=CRS_WGS84,
        )
    else:
        df["geometry"] = df["geometry"].apply(lambda b: shapely_wkb.loads(bytes(b)))
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=CRS_WGS84)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        from pyproj import CRS
        crs_wkt = CRS.from_user_input(CRS_WGS84).to_wkt()
        schema = _schema_with_crs(crs_wkt)
        with pq.ParquetWriter(output_path, schema, compression="snappy") as w:
            buffer = []
            for geom, valor in tqdm(
                zip(gdf.geometry, gdf["valor_pixel"]),
                total=len(gdf),
                desc="Gravando raster_clip",
                disable=not show_progress,
            ):
                buffer.append((geom, int(valor)))
                if len(buffer) >= 10_000:
                    _flush_raster(buffer, schema, w)
                    buffer.clear()
            if buffer:
                _flush_raster(buffer, schema, w)
                buffer.clear()

    return gdf


def _flush_raster(buffer, schema, writer):
    if not buffer:
        return
    geoms = [g.wkb for g, _ in buffer]
    vals = [int(v) for _, v in buffer]
    geom_col = pa.array(geoms, type=pa.binary())
    val_col = pa.array(vals, type=pa.int32())
    table = pa.Table.from_arrays([val_col, geom_col], schema=schema)
    writer.write_table(table)