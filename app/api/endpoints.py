from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Any, Dict
import os

from app.tasks.worker import analyze_task
from app.celery_app import celery_app

router = APIRouter()

class AnalyzeRequest(BaseModel):
    aoi_geojson: Dict[str, Any] = None
    min_level: int = 1
    max_level: int = 3
    network_type: str = "drive"
    road_buffer_m: float = 10.0
    raster: str = None
    edges: str = None

@router.post("/analyze")
def analyze(payload: AnalyzeRequest):
    # Converte o request para dicionário e adiciona um job_id único (o ID da task)
    task_payload = payload.dict()
    
    # Inicia a task no celery
    task = analyze_task.delay(task_payload)
    
    return {"task_id": task.id, "status": "processing"}

@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    task_result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }

@router.get("/download/{task_id}")
def download_result(task_id: str):
    """
    Faz o download do arquivo ZIP contendo os GeoJSON resultantes.
    """
    file_path = os.path.join("data", "outputs", task_id, "resultados.zip")
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=f"resultados_{task_id}.zip", media_type='application/zip')
    else:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou processamento ainda não concluído.")
