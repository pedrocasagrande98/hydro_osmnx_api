"""Relatorios CSV/JSON do pipeline hydro_mde."""

from __future__ import annotations

import csv
import json
import os
from typing import Dict

import geopandas as gpd

from hydro_mde.config import NIVEL_LABELS, NIVEL_PALETTE, NIVEL_PROFUNDIDADE


def write_report_per_level(by_level: Dict[int, gpd.GeoDataFrame],
                           edges_total: int,
                           edges_total_length_m: float,
                           output_dir: str,
                           show_progress: bool = True) -> Dict[str, str]:
    """Gera relatorio.csv, relatorio.json, e sumario por nivel.

    Retorna dict com paths gerados:
      - "csv"
      - "json"
      - "geojson_<nivel>"
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "relatorio.csv")
    json_path = os.path.join(output_dir, "relatorio.json")

    rows = []
    metrics_per_level = {}
    geojson_paths: Dict[int, str] = {}

    for nivel in (1, 2, 3):
        gdf = by_level[nivel]
        slug, desc = NIVEL_LABELS[nivel]
        n_afetadas = len(gdf)
        comp_afetado = float(gdf["comprimento_afetado_m"].sum()) if n_afetadas else 0.0
        comp_total_vias = float(gdf["comprimento_total_m"].sum()) if n_afetadas else 0.0
        pct_vias = (n_afetadas / edges_total * 100.0) if edges_total else 0.0

        rows.append({
            "nivel": nivel,
            "severidade": slug,
            "profundidade": desc,
            "cor": NIVEL_PALETTE[nivel],
            "n_vias_afetadas": n_afetadas,
            "pct_vias_total": round(pct_vias, 2),
            "comprimento_afetado_m": round(comp_afetado, 2),
            "comprimento_total_vias_m": round(comp_total_vias, 2),
        })

        metrics_per_level[slug] = {
            "nivel": nivel,
            "descricao": desc,
            "cor": NIVEL_PALETTE[nivel],
            "n_vias_afetadas": n_afetadas,
            "pct_vias_total": round(pct_vias, 2),
            "comprimento_afetado_m": round(comp_afetado, 2),
            "comprimento_total_vias_m": round(comp_total_vias, 2),
        }

        geojson_path = os.path.join(output_dir, f"vias_afetadas_nivel_{nivel}_{slug}.geojson")
        if not gdf.empty:
            gj = json.loads(gdf.to_json())
        else:
            gj = {"type": "FeatureCollection", "features": []}
        with open(geojson_path, "w", encoding="utf-8") as fp:
            json.dump(gj, fp, ensure_ascii=False)
        geojson_paths[nivel] = geojson_path

    with open(csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "edges_total": edges_total,
        "edges_total_length_m": round(edges_total_length_m, 2),
        "niveis": metrics_per_level,
    }
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2)

    if show_progress:
        print(f"  Relatorio CSV : {csv_path}")
        print(f"  Relatorio JSON: {json_path}")
        for nivel, p in geojson_paths.items():
            print(f"  GeoJSON nivel {nivel}: {p}")

    return {
        "csv": csv_path,
        "json": json_path,
        **{f"geojson_{n}": p for n, p in geojson_paths.items()},
    }