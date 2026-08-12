import os
import time
import zipfile
from typing import Dict, Any

from hydro_mde.config import (
    AOI_BUFFER_DEG,
    CRS_WGS84,
    EDGES_DEFAULT,
    OUTPUT_DIR,
    RASTER_PARQUET,
    UTM_SA_ALBERS,
)
from hydro_mde.aoi import build_aoi
from hydro_mde.clip_raster import clip_raster_to_aoi
from hydro_mde.crossing import find_affected_edges_by_level
from hydro_mde.fetch_roads import fetch_roads
from hydro_mde.report import write_report_per_level


def _geom_length_m(geom, transformer):
    from shapely.ops import transform as shp_transform
    try:
        projected = shp_transform(transformer.transform, geom)
        return projected.length
    except Exception:
        return 0.0


def run_hydro_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a pipeline geoespacial completa usando os dados do payload.
    """
    t0 = time.time()
    
    # Extrair parametros do payload com fallback para defaults
    edges = payload.get("edges", EDGES_DEFAULT)
    aoi_file = payload.get("aoi_file", None)
    buffer_deg = payload.get("buffer_deg", AOI_BUFFER_DEG)
    raster = payload.get("raster", RASTER_PARQUET)
    min_level = payload.get("min_level", 1)
    max_level = payload.get("max_level", 3)
    network_type = payload.get("network_type", "drive")
    road_buffer_m = payload.get("road_buffer_m", 10.0)
    utm_epsg = payload.get("utm_epsg", UTM_SA_ALBERS)
    offline = payload.get("offline", False)
    
    aoi_geojson = payload.get("aoi_geojson", None)
    
    # OUTPUT_DIR ajustado para usar /app/data/outputs no container
    output_dir = os.path.join("data", "outputs", payload.get("job_id", "default"))
    os.makedirs(output_dir, exist_ok=True)

    print(f"Iniciando pipeline para job {payload.get('job_id', 'default')}")
    
    # Se recebemos o GeoJSON diretamente no payload, salvamos ele num arquivo
    if aoi_geojson:
        import json
        aoi_file = os.path.join(output_dir, "input_aoi.geojson")
        with open(aoi_file, "w", encoding="utf-8") as f:
            json.dump(aoi_geojson, f)

    # 1. AOI
    aoi_path = os.path.join(output_dir, "aoi.geojson")
    aoi = build_aoi(
        edges_path=edges,
        aoi_file=aoi_file,
        buffer_deg=buffer_deg,
        output_path=aoi_path,
    )

    # 2. Clip Raster
    raster_path = os.path.join(output_dir, "raster_clip.parquet")
    raster_gdf = clip_raster_to_aoi(
        aoi,
        raster_path=raster,
        min_level=min_level,
        max_level=max_level,
        output_path=raster_path,
    )
    
    if raster_gdf.empty:
        return {"status": "completed", "message": "Nenhum poligono do raster dentro do AOI.", "result_zip": None}

    # 3. Fetch Roads
    edges_path = os.path.join(output_dir, "edges_aoi.geojson")
    edges_gdf = fetch_roads(
        aoi,
        network_type=network_type,
        offline=offline,
        edges_path=edges,
        output_path=edges_path,
    )

    if edges_gdf.empty:
        return {"status": "completed", "message": "Nenhuma via encontrada no AOI.", "result_zip": None}

    edges_total = len(edges_gdf)
    edges_total_length_m = 0.0
    if edges_total:
        from pyproj import CRS as PyprojCRS, Transformer
        crs_aoi = edges_gdf.crs
        if crs_aoi is None:
            crs_aoi = CRS_WGS84
        transformer = Transformer.from_crs(
            PyprojCRS.from_user_input(crs_aoi),
            PyprojCRS.from_user_input(utm_epsg),
            always_xy=True,
        )
        edges_total_length_m = sum(
            _geom_length_m(g, transformer) for g in edges_gdf.geometry
        )

    # 4. Cruzamento
    by_level = find_affected_edges_by_level(
        edges_gdf,
        raster_gdf,
        road_buffer_m=road_buffer_m,
        utm_epsg=utm_epsg,
    )

    # Gerando Relatórios
    paths = write_report_per_level(
        by_level,
        edges_total=edges_total,
        edges_total_length_m=edges_total_length_m,
        output_dir=output_dir,
    )

    # Zipando resultados
    zip_filename = "resultados.zip"
    zip_path = os.path.join(output_dir, zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file != zip_filename:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)

    elapsed = time.time() - t0

    return {
        "status": "completed",
        "message": "Processamento concluido com sucesso.",
        "tempo_segundos": elapsed,
        "vias_total": edges_total,
        "vias_comprimento_m": edges_total_length_m,
        "result_zip": zip_path
    }
