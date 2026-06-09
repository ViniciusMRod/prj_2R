"""
POST /converter-excel
Recebe o Excel editado pelo técnico e insere registros em ValidacaoPendente.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config.database import get_db
from src.database.models import ValidacaoPendente
from src.extraction.excel_converter import converter_excel_para_registros

router = APIRouter(tags=["Conversão"])


@router.post("/converter-excel", summary="Converte Excel editado e insere na fila de validação")
async def converter_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Recebe o .xlsx editado pelo técnico de segurança.
    Converte para JSON e insere um registro em ValidacaoPendente por empresa.
    Retorna lista de IDs inseridos.
    """
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .xlsx")

    conteudo = await file.read()
    try:
        registros = converter_excel_para_registros(conteudo)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Erro ao processar Excel: {exc}")

    if not registros:
        raise HTTPException(status_code=422, detail="Nenhum registro encontrado no Excel.")

    inseridos = []
    for reg in registros:
        nome_arquivo = reg.get("arquivo") or "desconhecido.pdf"
        v = ValidacaoPendente(
            pcmso_filename=nome_arquivo,
            dados_extraidos=reg,
        )
        db.add(v)
        db.flush()  # gera o id antes do commit
        inseridos.append({"id": v.id, "arquivo": nome_arquivo})

    db.commit()

    return {
        "inseridos": len(inseridos),
        "registros": inseridos,
    }
