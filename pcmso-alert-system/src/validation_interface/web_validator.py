"""
Interface web FastAPI para validação técnica de PCMSOs.
Ponto central da aplicação — agrega todas as rotas do sistema.
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config.database import get_db, test_connection
from src.database.models import (
    Colaborador, CargoExame, Empresa, Exame, StatusExame,
    StatusValidacao, TipoExame, ValidacaoPendente,
)
from src.database.queries import get_validacoes_pendentes
from src.demandas.demand_interface import colabs_router, router as demandas_router
from src.extraction.duplicate_checker import (
    ResultadoDuplicata, calcular_hash_arquivo, verificar_duplicata,
)
from src.extraction.pdf_extractor import extrair_pcmso, salvar_json_extracao
from src.extraction.validators import validar_cnpj, validar_cpf, validar_dados_extraidos

load_dotenv()
logger = logging.getLogger(__name__)

PCMSO_RAW_PATH      = Path(os.getenv("PCMSO_RAW_PATH", "data/pcmso_raw/"))
PCMSO_PENDING_PATH  = Path(os.getenv("PCMSO_PENDING_PATH", "data/pcmso_pending_validation/"))
PCMSO_PROCESSED_PATH = Path(os.getenv("PCMSO_PROCESSED_PATH", "data/pcmso_processed/"))

app = FastAPI(title="PCMSO Alert System", version="1.0.0")

# Templates e rotas externas
templates = Jinja2Templates(directory="src/validation_interface/templates")
app.include_router(demandas_router)
app.include_router(colabs_router)

# Injeta `today` em todos os templates Jinja2
@app.middleware("http")
async def add_template_globals(request: Request, call_next):
    response = await call_next(request)
    return response

templates.env.globals["today"] = lambda: datetime.today().date()


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    pendentes = get_validacoes_pendentes(db)
    from src.database.queries import listar_empresas_ativas
    empresas = listar_empresas_ativas(db)
    return templates.TemplateResponse("pending_list.html", {
        "request": request,
        "pendentes": pendentes,
        "empresas": empresas,
    })


# ---------------------------------------------------------------------------
# Validação — lista
# ---------------------------------------------------------------------------

@app.get("/validacao", response_class=HTMLResponse)
async def lista_validacoes(request: Request, db: Session = Depends(get_db)):
    pendentes = get_validacoes_pendentes(db)
    return templates.TemplateResponse("pending_list.html", {
        "request": request,
        "pendentes": pendentes,
    })


# ---------------------------------------------------------------------------
# Validação — detalhe
# ---------------------------------------------------------------------------

@app.get("/validacao/{validacao_id}", response_class=HTMLResponse)
async def detalhe_validacao(
    request: Request,
    validacao_id: int,
    db: Session = Depends(get_db),
):
    v = db.get(ValidacaoPendente, validacao_id)
    if not v:
        raise HTTPException(status_code=404, detail="Validação não encontrada")

    dados = v.dados_extraidos or {"empresa": {}, "colaboradores": [], "exames": [], "cargo_exames": []}
    resultado_validacao = validar_dados_extraidos(dados)

    cnpj_valido = validar_cnpj(dados.get("empresa", {}).get("cnpj", ""))
    cpfs_invalidos = {
        ci["valor"] for ci in resultado_validacao["colaboradores_invalidos"]
    }

    aviso_duplicata = None
    if dados.get("_duplicata"):
        aviso_duplicata = dados["_duplicata"]

    return templates.TemplateResponse("validate_pcmso.html", {
        "request": request,
        "validacao": v,
        "dados": dados,
        "erros_validacao": resultado_validacao["erros"],
        "avisos_validacao": resultado_validacao["avisos"],
        "colaboradores_invalidos": resultado_validacao["colaboradores_invalidos"],
        "cnpj_valido": cnpj_valido,
        "cpfs_invalidos": cpfs_invalidos,
        "aviso_duplicata": aviso_duplicata,
    })


# ---------------------------------------------------------------------------
# Validação — aprovar
# ---------------------------------------------------------------------------

@app.post("/validacao/{validacao_id}/aprovar")
async def aprovar_validacao(
    request: Request,
    validacao_id: int,
    acao: str = Form("aprovar"),
    cnpj: str = Form(...),
    razao_social: str = Form(...),
    ano_referencia: int = Form(...),
    email_sso: str = Form(""),
    whatsapp_sso: str = Form(""),
    observacoes_tecnico: str = Form(""),
    validado_por: str = Form("Técnico"),
    total_colaboradores: int = Form(0),
    db: Session = Depends(get_db),
):
    v = db.get(ValidacaoPendente, validacao_id)
    if not v:
        raise HTTPException(status_code=404, detail="Validação não encontrada")

    from sqlalchemy import select
    from src.extraction.duplicate_checker import registrar_versao
    from dateutil.relativedelta import relativedelta
    import re

    # 1. Upsert empresa
    empresa = db.scalar(select(Empresa).where(
        Empresa.cnpj == re.sub(r"[^\d]", "", cnpj)
        if len(re.sub(r"[^\d]", "", cnpj)) == 14
        else Empresa.cnpj == cnpj
    ))
    if not empresa:
        empresa = Empresa(
            razao_social=razao_social,
            cnpj=cnpj,
            email_sso=email_sso or "sso@empresa.com.br",
            whatsapp_sso=whatsapp_sso,
        )
        db.add(empresa)
        db.flush()

    dados = v.dados_extraidos or {}

    # 2. Coletar dados corrigidos do formulário (se acao == editar_aprovar)
    form_data = await request.form()
    colaboradores_dados = dados.get("colaboradores", [])
    if acao == "editar_aprovar":
        colaboradores_corrigidos = []
        for i in range(total_colaboradores):
            nome = form_data.get(f"col_nome_{i}", "")
            cpf  = form_data.get(f"col_cpf_{i}", "")
            cargo = form_data.get(f"col_cargo_{i}", "")
            setor = form_data.get(f"col_setor_{i}", "")
            if nome:
                colaboradores_corrigidos.append({
                    "nome_completo": nome, "cpf": cpf,
                    "cargo": cargo, "setor": setor,
                })
        colaboradores_dados = colaboradores_corrigidos

    # 3. Inserir colaboradores
    from src.extraction.validators import formatar_cpf
    for col_data in colaboradores_dados:
        cpf_fmt = formatar_cpf(col_data.get("cpf", ""))
        existente = db.scalar(select(Colaborador).where(Colaborador.cpf == cpf_fmt))
        if not existente and validar_cpf(col_data.get("cpf", "")):
            col = Colaborador(
                empresa_id=empresa.id,
                nome_completo=col_data.get("nome_completo", ""),
                cpf=cpf_fmt,
                cargo=col_data.get("cargo", ""),
                setor=col_data.get("setor", ""),
                ativo=True,
            )
            db.add(col)

    # 4. Inserir mapeamentos cargo × exames
    from datetime import date
    for ce_data in dados.get("cargo_exames", []):
        tipo_nome = ce_data.get("tipo_exame", "").strip()
        if not tipo_nome:
            continue
        tipo = db.scalar(select(TipoExame).where(TipoExame.nome == tipo_nome))
        if not tipo:
            tipo = TipoExame(
                nome=tipo_nome,
                periodicidade_meses=ce_data.get("periodicidade_meses") or 12,
            )
            db.add(tipo)
            db.flush()

        cargo_nome = ce_data.get("cargo", "").strip()
        if cargo_nome:
            existente_ce = db.scalar(select(CargoExame).where(
                CargoExame.empresa_id == empresa.id,
                CargoExame.cargo == cargo_nome,
                CargoExame.tipo_exame_id == tipo.id,
            ))
            if not existente_ce:
                db.add(CargoExame(
                    empresa_id=empresa.id,
                    cargo=cargo_nome,
                    setor=ce_data.get("setor", ""),
                    risco=ce_data.get("risco", ""),
                    tipo_exame_id=tipo.id,
                    periodicidade_meses=ce_data.get("periodicidade_meses"),
                ))

    db.flush()

    # 5. Inserir exames
    from dateutil.relativedelta import relativedelta
    for ex_data in dados.get("exames", []):
        tipo_nome = ex_data.get("tipo_exame", "").strip()
        colaborador_nome = ex_data.get("colaborador_nome", "").strip()
        if not tipo_nome or not colaborador_nome:
            continue

        tipo = db.scalar(select(TipoExame).where(TipoExame.nome == tipo_nome))
        if not tipo:
            continue

        col = db.scalar(select(Colaborador).where(
            Colaborador.empresa_id == empresa.id,
            Colaborador.nome_completo == colaborador_nome,
        ))
        if not col:
            continue

        data_proximo = ex_data.get("data_proximo_exame")
        if not data_proximo:
            periodo = ex_data.get("periodicidade_meses") or tipo.periodicidade_meses
            data_ultimo = ex_data.get("data_ultimo_exame")
            base = date.fromisoformat(str(data_ultimo)) if data_ultimo else date.today()
            data_proximo = base + relativedelta(months=periodo)
        elif isinstance(data_proximo, str):
            data_proximo = date.fromisoformat(data_proximo)

        db.add(Exame(
            colaborador_id=col.id,
            tipo_exame_id=tipo.id,
            data_ultimo_exame=ex_data.get("data_ultimo_exame"),
            data_proximo_exame=data_proximo,
            status=StatusExame.PENDENTE,
        ))

    # 6. Registrar versão do PCMSO
    hash_arq = dados.get("hash", "")
    if hash_arq:
        registrar_versao(db, empresa.id, ano_referencia,
                         v.pcmso_filename, hash_arq)

    # 7. Atualizar status da validação
    v.status = StatusValidacao.APROVADO
    v.observacoes_tecnico = observacoes_tecnico
    v.validado_por = validado_por
    v.data_validacao = datetime.now()
    v.empresa_id = empresa.id

    db.commit()

    # 8. Mover PDF para processados
    _mover_arquivo(v.pcmso_filename, PCMSO_PENDING_PATH, PCMSO_PROCESSED_PATH)

    logger.info(f"PCMSO validado e importado: {v.pcmso_filename} empresa={empresa.razao_social}")
    return RedirectResponse(url=f"/validacao?mensagem_sucesso=PCMSO+importado+com+sucesso", status_code=303)


# ---------------------------------------------------------------------------
# Validação — rejeitar
# ---------------------------------------------------------------------------

@app.post("/validacao/{validacao_id}/rejeitar")
async def rejeitar_validacao(
    validacao_id: int,
    observacoes_tecnico: str = Form(""),
    db: Session = Depends(get_db),
):
    v = db.get(ValidacaoPendente, validacao_id)
    if not v:
        raise HTTPException(status_code=404, detail="Validação não encontrada")

    v.status = StatusValidacao.REJEITADO
    v.observacoes_tecnico = observacoes_tecnico
    v.data_validacao = datetime.now()
    db.commit()

    logger.info(f"PCMSO rejeitado: {v.pcmso_filename}")
    return RedirectResponse(url="/validacao", status_code=303)


# ---------------------------------------------------------------------------
# API endpoints para n8n
# ---------------------------------------------------------------------------

@app.post("/api/extrair-pcmso", response_class=JSONResponse)
async def api_extrair_pcmso(
    request: Request,
    db: Session = Depends(get_db),
):
    """Recebe nome do arquivo, extrai e insere na fila de validação."""
    body = await request.json()
    filename = body.get("filename", "")
    filepath = PCMSO_RAW_PATH / filename

    if not filepath.exists():
        return JSONResponse({"ok": False, "erro": f"Arquivo não encontrado: {filename}"}, status_code=404)

    try:
        dados = extrair_pcmso(filepath)

        # Verificar duplicata
        empresa_cnpj = dados.get("empresa", {}).get("cnpj", "")
        from sqlalchemy import select
        empresa = db.scalar(select(Empresa).where(Empresa.cnpj == empresa_cnpj)) if empresa_cnpj else None
        empresa_id = empresa.id if empresa else None
        ano = dados.get("empresa", {}).get("ano_referencia", datetime.now().year)

        resultado_dup, versao_dup, msg_dup = verificar_duplicata(
            db, dados["hash"], empresa_id or 0, ano
        )

        if resultado_dup == ResultadoDuplicata.DUPLICATA_EXATA:
            return JSONResponse({"ok": False, "duplicata": True, "mensagem": msg_dup})

        dados["_duplicata"] = msg_dup if resultado_dup == ResultadoDuplicata.NOVA_VERSAO else None

        # Mover para pending
        dest = PCMSO_PENDING_PATH / filename
        shutil.move(str(filepath), str(dest))
        salvar_json_extracao(dados, PCMSO_PENDING_PATH / f"{filepath.stem}.json")

        # Inserir na fila
        v = ValidacaoPendente(
            pcmso_filename=filename,
            empresa_id=empresa_id,
            dados_extraidos=dados,
        )
        db.add(v)
        db.commit()
        db.refresh(v)

        return JSONResponse({
            "ok": True,
            "validacao_id": v.id,
            "colaboradores": len(dados.get("colaboradores", [])),
            "exames": len(dados.get("exames", [])),
            "mensagem": msg_dup,
        })

    except Exception as e:
        logger.error(f"Erro ao extrair {filename}: {e}")
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=500)


@app.post("/api/processar-alertas", response_class=JSONResponse)
async def api_processar_alertas(db: Session = Depends(get_db)):
    """Trigger para o motor de alertas diários (chamado pelo n8n)."""
    from src.business_logic.alert_engine import processar_alertas_diarios
    resultado = processar_alertas_diarios(db)
    return JSONResponse(resultado)


@app.get("/api/relatorio-mensal", response_class=JSONResponse)
async def api_relatorio_mensal(db: Session = Depends(get_db)):
    """Gera relatório mensal consolidado (chamado pelo n8n)."""
    from src.business_logic.report_builder import gerar_relatorio_mensal
    resultado = gerar_relatorio_mensal(db)
    return JSONResponse(resultado)


@app.get("/health")
async def health():
    return {"status": "ok", "db": test_connection()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mover_arquivo(filename: str, origem: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    src = origem / filename
    if src.exists():
        shutil.move(str(src), str(destino / filename))
        # Mover JSON de extração também se existir
        json_src = origem / f"{Path(filename).stem}.json"
        if json_src.exists():
            shutil.move(str(json_src), str(destino / json_src.name))
