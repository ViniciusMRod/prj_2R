"""
POST /extrair-lote
Recebe N PDFs via multipart/form-data, processa em paralelo e retorna Excel.
"""
from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from src.extraction.pdf_extractor import extrair_pcmso
from src.extraction.excel_builder import gerar_excel

router = APIRouter(tags=["Extração"])


def _processar_pdf(upload: UploadFile) -> dict:
    """Salva o upload em arquivo temporário e extrai os dados."""
    conteudo = upload.file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(conteudo)
        tmp_path = Path(tmp.name)

    try:
        resultado = extrair_pcmso(tmp_path)
        # Preserva o nome original do arquivo enviado
        resultado["arquivo"] = upload.filename or tmp_path.name
    finally:
        tmp_path.unlink(missing_ok=True)

    return resultado


@router.post("/extrair-lote", summary="Extrai N PDFs e retorna Excel para revisão")
async def extrair_lote(files: list[UploadFile] = File(...)):
    """
    Recebe um ou mais PDFs de PCMSO.
    Processa em paralelo (ThreadPoolExecutor) e retorna arquivo .xlsx
    com 5 abas de dados + 1 aba de erros.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    resultados = []
    erros_fatais = []

    with ThreadPoolExecutor(max_workers=min(len(files), 8)) as executor:
        futures = {executor.submit(_processar_pdf, f): f.filename for f in files}
        for future in as_completed(futures):
            nome = futures[future]
            try:
                resultados.append(future.result())
            except Exception as exc:
                erros_fatais.append({"arquivo": nome, "erros_extracao": [str(exc)]})

    resultados.extend(erros_fatais)

    excel_bytes = gerar_excel(resultados)
    nome_arquivo = f"PCMSO_Lote_{date.today().isoformat()}.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
