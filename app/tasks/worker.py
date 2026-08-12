import time
from app.celery_app import celery_app
from typing import Dict, Any
from app.services.geospatial import run_hydro_pipeline

@celery_app.task(bind=True)
def analyze_task(self, payload: Dict[str, Any]):
    """
    Background task para executar a pipeline geoespacial.
    """
    # Injecta o id da task no payload para que o serviço geoespacial saiba onde salvar
    payload['job_id'] = self.request.id
    
    self.update_state(state='PROGRESS', meta={'status': 'Iniciando processamento'})
    
    # Chama o servico geoespacial real
    result = run_hydro_pipeline(payload)
    
    return result
