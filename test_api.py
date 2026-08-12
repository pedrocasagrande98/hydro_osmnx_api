import time
import requests
import json
import os
import sys

# Configuração
HOST = "http://187.77.61.11:8000"

print(f"Iniciando testes na API: {HOST}\n")

# 1. Teste de Health Check
print("1. Testando Health Check...")
try:
    response = requests.get(f"{HOST}/health", timeout=10)
    if response.status_code == 200:
        try:
            print("[OK] Health Check:", response.json())
        except Exception:
            print("[OK] Health Check (Non-JSON):", response.text[:200])
    else:
        print("[X] Falha no Health Check:", response.status_code, response.text[:200])
except Exception as e:
    print("[X] Erro de conexao:", e)
    sys.exit(1)

# 2. Teste de Disparo de Análise (Inicia a Task no Celery)
print("\n2. Disparando Job de Analise (Celery)...")
payload = {
    "aoi_geojson": {
        "type": "FeatureCollection",
        "features": [] 
    },
    "min_level": 1,
    "max_level": 3,
    "network_type": "drive",
    "road_buffer_m": 10.0
}

task_id = None
try:
    response = requests.post(f"{HOST}/api/v1/analyze", json=payload, timeout=15)
    if response.status_code == 200:
        data = response.json()
        task_id = data.get("task_id")
        print(f"[OK] Job criado com sucesso! Task ID: {task_id}")
    else:
        print("[X] Falha ao criar Job:", response.status_code, response.text[:200])
except Exception as e:
    print("[X] Erro de conexao no POST:", e)

# 3. Teste de Polling (Acompanhando o status da Task)
if task_id:
    print("\n3. Acompanhando o status da Task (Aguarde)...")
    max_tentativas = 15
    tentativa = 0
    status = "pending"
    
    while tentativa < max_tentativas and status not in ["SUCCESS", "FAILURE", "completed"]:
        time.sleep(5)
        try:
            res = requests.get(f"{HOST}/api/v1/tasks/{task_id}", timeout=10)
            if res.status_code == 200:
                data = res.json()
                status = data.get("status", "")
                
                if data.get("result") and isinstance(data.get("result"), dict):
                     if data["result"].get("status") == "completed":
                         status = "completed"
                
                print(f"   [{tentativa+1}/{max_tentativas}] Status atual: {status}")
            else:
                print(f"   [X] Erro ao checar status: {res.status_code}")
        except Exception as e:
            print("   [X] Erro de conexao no GET:", e)
        
        tentativa += 1

    if status in ["SUCCESS", "completed"]:
        print("[OK] Processamento concluido!")
        
        # 4. Teste de Download do Resultado
        print(f"\n4. Testando Download do arquivo ZIP gerado...")
        download_url = f"{HOST}/api/v1/download/{task_id}"
        print(f"   Acessando: {download_url}")
        try:
            r = requests.get(download_url, stream=True, timeout=10)
            if r.status_code == 200:
                filename = f"resultado_teste_{task_id}.zip"
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"[OK] Download concluido! Arquivo salvo como: {filename} ({os.path.getsize(filename)} bytes)")
            else:
                print(f"[X] Falha no Download. Status Code: {r.status_code}")
                print("   Detalhe:", r.text[:200])
        except Exception as e:
             print("   [X] Erro no download:", e)
    else:
        print("[!] O processamento nao terminou a tempo ou falhou. Verifique os logs.")

print("\nBateria de testes finalizada.")
