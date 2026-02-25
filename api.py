import json
import os
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Downdetector API")

JSON_FILE = "/app/data/downdetector_status.json"
def load_json():
    if not os.path.exists(JSON_FILE):
        return []
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


@app.get("/status")
def get_all():
    return load_json()


@app.get("/status/{empresa}")
def get_by_empresa(empresa: str):
    data = load_json()
    result = next((e for e in data if e["empresa"].lower() == empresa.lower()), None)
    if not result:
        raise HTTPException(status_code=404, detail=f"Empresa '{empresa}' não encontrada")
    return result


@app.get("/status/event/danger")
def get_danger():
    data = load_json()
    return [e for e in data if e["company_status"] == "danger"]
