"""CLI principal do pipeline hydro_mde refatorado.

Uso:
    python -m run                                          # usa defaults
    python -m run --offline                                # reusa edges.geojson
    python -m run --aoi-file meu_aoi.geojson
    python -m run --network-type drive_service --min-level 2
"""

from __future__ import annotations

import argparse
import sys
import uuid

from hydro_mde.config import (
    AOI_BUFFER_DEG,
    EDGES_DEFAULT,
    OUTPUT_DIR,
    RASTER_PARQUET,
    UTM_SA_ALBERS,
)
from app.services.geospatial import run_hydro_pipeline

def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run",
        description="CLI Pipeline hydro_mde.",
    )
    p.add_argument("--edges", default=EDGES_DEFAULT, help="Caminho das vias de entrada")
    p.add_argument("--aoi-file", default=None, help="Geometria/FeatureCollection arbitraria")
    p.add_argument("--buffer-deg", type=float, default=AOI_BUFFER_DEG, help="Buffer do AOI em graus")
    p.add_argument("--raster", default=RASTER_PARQUET, help="GeoParquet de entrada")
    p.add_argument("--min-level", type=int, default=1, choices=(1, 2, 3), help="Nivel minimo GLOFAS")
    p.add_argument("--max-level", type=int, default=3, choices=(1, 2, 3), help="Nivel maximo GLOFAS")
    p.add_argument("--network-type", default="drive", choices=("drive", "drive_service", "walk", "bike", "all"))
    p.add_argument("--road-buffer-m", type=float, default=10.0, help="Buffer das vias em metros")
    p.add_argument("--utm-epsg", default=UTM_SA_ALBERS, help="Projecao metrica")
    p.add_argument("--offline", action="store_true", help="Reusa edges.geojson local")
    p.add_argument("--output-dir", default=OUTPUT_DIR, help="Diretorio de saida")
    return p.parse_args(argv)

def main(argv=None) -> int:
    args = parse_args(argv)
    
    payload = {
        "job_id": f"cli_{uuid.uuid4().hex[:8]}",
        "edges": args.edges,
        "aoi_file": args.aoi_file,
        "buffer_deg": args.buffer_deg,
        "raster": args.raster,
        "min_level": args.min_level,
        "max_level": args.max_level,
        "network_type": args.network_type,
        "road_buffer_m": args.road_buffer_m,
        "utm_epsg": args.utm_epsg,
        "offline": args.offline
    }

    print("=" * 70)
    print("hydro_mde | CLI delegando para pipeline")
    print("=" * 70)
    
    result = run_hydro_pipeline(payload)
    
    print("=" * 70)
    print("RESULTADO")
    print("=" * 70)
    print(f"Status: {result.get('status')}")
    print(f"Message: {result.get('message')}")
    print(f"Tempo total: {result.get('tempo_segundos', 0):.1f}s")
    if result.get("result_zip"):
        print(f"Zip gerado: {result['result_zip']}")

    return 0

if __name__ == "__main__":
    sys.exit(main())