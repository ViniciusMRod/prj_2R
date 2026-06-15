"""
POST /extrair-lote
Recebe N PDFs via multipart/form-data, grava em staging e cria job pendente.
"""
from __future__ import annotations

import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from src.database.models import Empresa, LoteJob, StatusLote
from src.extraction.duplicate_checker import ResultadoDuplicata, verificar_duplicata

router = APIRouter(tags=["Extração"])

PCMSO_LOTE_STAGING = Path(os.getenv("PCMSO_LOTE_STAGING", "data/pcmso_lote_staging/"))


# Reusado pelo worker de lote (Fase 3); o endpoint assíncrono não o chama.
def _classificar_versionamento(db: Session, resultado: dict) -> None:
    """
    Pré-checa duplicata/versão para um resultado de extração e grava
    `status_pcmso` + `mensagem_versao` (consumidos pela aba Metadados).
    Roda sequencial na thread principal — a sessão SQLAlchemy não é thread-safe.
    """
    if not resultado.get("hash"):
        resultado["status_pcmso"] = "NOVO"
        return

    empresa_cnpj = (resultado.get("empresa") or {}).get("cnpj", "")
    empresa = db.scalar(select(Empresa).where(Empresa.cnpj == empresa_cnpj)) if empresa_cnpj else None
    empresa_id = empresa.id if empresa else None
    ano = (resultado.get("empresa") or {}).get("ano_referencia", datetime.now().year)

    resultado_dup, _versao, msg = verificar_duplicata(db, resultado["hash"], empresa_id or 0, ano)
    resultado["status_pcmso"] = resultado_dup.value if hasattr(resultado_dup, "value") else str(resultado_dup)
    resultado["mensagem_versao"] = msg if resultado_dup != ResultadoDuplicata.NOVO_ARQUIVO else ""


@router.post("/extrair-lote", status_code=202,
             summary="Aceita N PDFs e cria um job de extração assíncrono")
async def extrair_lote(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Recebe N PDFs, grava em staging e cria um job 'pendente'.
    Devolve o job_uuid imediatamente (HTTP 202). O worker processa em background.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    job_uuid = str(uuid.uuid4())
    staging = PCMSO_LOTE_STAGING / job_uuid
    staging.mkdir(parents=True, exist_ok=True)

    total = 0
    for f in files:
        nome = f.filename or f"arquivo_{total}.pdf"
        with open(staging / nome, "wb") as out:
            shutil.copyfileobj(f.file, out)
        total += 1

    job = LoteJob(
        job_uuid=job_uuid,
        status=StatusLote.PENDENTE,
        total_pdfs=total,
        staging_dir=str(staging),
    )
    db.add(job)
    db.commit()

    return {"job_uuid": job_uuid, "total_pdfs": total, "status": StatusLote.PENDENTE.value}


_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/lote/{job_uuid}/excel", summary="Download do Excel consolidado do lote")
def download_excel_lote(job_uuid: str, db: Session = Depends(get_db)):
    job = db.scalar(select(LoteJob).where(LoteJob.job_uuid == job_uuid))
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if job.status == StatusLote.FALHOU:
        raise HTTPException(status_code=422, detail=job.erro_detalhe or "Processamento falhou.")
    if job.status != StatusLote.CONCLUIDO or not job.excel_path:
        raise HTTPException(status_code=409, detail="Lote ainda em processamento.")
    return FileResponse(job.excel_path, media_type=_XLSX_MIME,
                        filename=Path(job.excel_path).name)


@router.get("/lote/{job_uuid}", summary="Status e progresso de um job de lote")
def status_lote(job_uuid: str, db: Session = Depends(get_db)):
    job = db.scalar(select(LoteJob).where(LoteJob.job_uuid == job_uuid))
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return {
        "job_uuid": job.job_uuid,
        "status": job.status.value,
        "total_pdfs": job.total_pdfs,
        "processados": job.processados,
        "com_erro": job.com_erro,
        "excel_pronto": job.status == StatusLote.CONCLUIDO,
    }
