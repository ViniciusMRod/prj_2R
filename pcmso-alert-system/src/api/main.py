"""
App FastAPI — PCMSO Alert System API
Endpoints de extração em lote e conversão de Excel.
"""
from fastapi import FastAPI

from src.api.routes.extracao import router as router_extracao
from src.api.routes.conversao import router as router_conversao

app = FastAPI(
    title="PCMSO Alert System API",
    description="Extração em lote de PCMSOs e conversão de Excel para fila de validação.",
    version="1.0.0",
)

app.include_router(router_extracao)
app.include_router(router_conversao)


@app.get("/health")
def health():
    return {"status": "ok"}
