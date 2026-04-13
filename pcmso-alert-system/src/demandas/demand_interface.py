"""
Rotas FastAPI para gestão de demandas e colaboradores.
Interface web amigável para técnicos de segurança — sem necessidade de SQL.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from src.database.models import (
    Colaborador,
    Demanda,
    Empresa,
    StatusDemanda,
    TipoMovimentacao,
)
from src.database.queries import (
    get_colaboradores_por_empresa,
    get_demandas_ativas,
    listar_cargos_por_empresa,
    listar_empresas_ativas,
)
from src.demandas.demand_manager import (
    criar_colaborador,
    gerar_demanda,
    inativar_colaborador,
)
from src.extraction.validators import validar_cpf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demandas", tags=["Demandas"])
templates = Jinja2Templates(directory="src/demandas/templates")


# ---------------------------------------------------------------------------
# Página principal — lista de demandas
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def listar_demandas(
    request: Request,
    empresa_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    empresas = listar_empresas_ativas(db)
    demandas = get_demandas_ativas(db, empresa_id=empresa_id)
    return templates.TemplateResponse("demandas_lista.html", {
        "request": request,
        "demandas": demandas,
        "empresas": empresas,
        "empresa_id_selecionada": empresa_id,
    })


# ---------------------------------------------------------------------------
# Nova demanda — formulário
# ---------------------------------------------------------------------------

@router.get("/nova", response_class=HTMLResponse)
async def form_nova_demanda(
    request: Request,
    empresa_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    empresas = listar_empresas_ativas(db)
    colaboradores = get_colaboradores_por_empresa(db, empresa_id) if empresa_id else []
    cargos = listar_cargos_por_empresa(db, empresa_id) if empresa_id else []

    return templates.TemplateResponse("demanda_nova.html", {
        "request": request,
        "empresas": empresas,
        "colaboradores": colaboradores,
        "cargos": cargos,
        "empresa_id_selecionada": empresa_id,
        "tipos_movimentacao": [t.value for t in TipoMovimentacao],
    })


@router.post("/nova")
async def criar_nova_demanda(
    request: Request,
    empresa_id: int = Form(...),
    colaborador_id: Optional[int] = Form(None),
    cargo: str = Form(...),
    tipo_movimentacao: str = Form(...),
    tecnico_responsavel: str = Form(""),
    observacoes: str = Form(""),
    # Campos para novo colaborador (admissional)
    novo_nome: str = Form(""),
    novo_cpf: str = Form(""),
    novo_setor: str = Form(""),
    nova_data_admissao: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    tipo_mov = TipoMovimentacao(tipo_movimentacao)
    colabs = get_colaboradores_por_empresa(db, empresa_id)
    empresas = listar_empresas_ativas(db)

    # Se admissional e colaborador novo, criar antes
    if tipo_mov == TipoMovimentacao.ADMISSIONAL and not colaborador_id:
        if not novo_nome or not novo_cpf:
            return templates.TemplateResponse("demanda_nova.html", {
                "request": request,
                "erro": "Para admissional, informe nome e CPF do novo colaborador.",
                "empresas": empresas,
                "colaboradores": colabs,
                "cargos": listar_cargos_por_empresa(db, empresa_id),
                "empresa_id_selecionada": empresa_id,
                "tipos_movimentacao": [t.value for t in TipoMovimentacao],
            })

        if not validar_cpf(novo_cpf):
            return templates.TemplateResponse("demanda_nova.html", {
                "request": request,
                "erro": f"CPF inválido: {novo_cpf}",
                "empresas": empresas,
                "colaboradores": colabs,
                "cargos": listar_cargos_por_empresa(db, empresa_id),
                "empresa_id_selecionada": empresa_id,
                "tipos_movimentacao": [t.value for t in TipoMovimentacao],
            })

        data_adm = None
        if nova_data_admissao:
            try:
                from datetime import datetime
                data_adm = datetime.strptime(nova_data_admissao, "%Y-%m-%d").date()
            except ValueError:
                pass

        novo_col = criar_colaborador(
            db, empresa_id, novo_nome, novo_cpf, cargo, novo_setor, data_adm
        )
        colaborador_id = novo_col.id

    if not colaborador_id:
        return templates.TemplateResponse("demanda_nova.html", {
            "request": request,
            "erro": "Selecione ou cadastre um colaborador.",
            "empresas": empresas,
            "colaboradores": colabs,
            "cargos": listar_cargos_por_empresa(db, empresa_id),
            "empresa_id_selecionada": empresa_id,
            "tipos_movimentacao": [t.value for t in TipoMovimentacao],
        })

    # Se demissional, inativar colaborador
    if tipo_mov == TipoMovimentacao.DEMISSIONAL:
        inativar_colaborador(db, colaborador_id)

    resultado = gerar_demanda(
        db=db,
        empresa_id=empresa_id,
        colaborador_id=colaborador_id,
        cargo=cargo,
        tipo_movimentacao=tipo_mov,
        tecnico_responsavel=tecnico_responsavel,
        observacoes=observacoes,
    )

    return templates.TemplateResponse("demanda_resultado.html", {
        "request": request,
        "demanda": resultado["demanda"],
        "exames_criados": resultado["exames_criados"],
        "aviso_sem_mapeamento": resultado["exames_sem_mapeamento"],
        "mensagem": resultado["mensagem"],
    })


# ---------------------------------------------------------------------------
# Detalhe de uma demanda
# ---------------------------------------------------------------------------

@router.get("/{demanda_id}", response_class=HTMLResponse)
async def detalhe_demanda(
    request: Request,
    demanda_id: int,
    db: Session = Depends(get_db),
):
    demanda = db.get(Demanda, demanda_id)
    if not demanda:
        raise HTTPException(status_code=404, detail="Demanda não encontrada")
    return templates.TemplateResponse("demanda_detalhe.html", {
        "request": request,
        "demanda": demanda,
    })


# ---------------------------------------------------------------------------
# Rotas de Colaboradores (interface estilo planilha)
# ---------------------------------------------------------------------------

colabs_router = APIRouter(prefix="/colaboradores", tags=["Colaboradores"])
colabs_templates = Jinja2Templates(directory="src/demandas/templates")


@colabs_router.get("/", response_class=HTMLResponse)
async def listar_colaboradores(
    request: Request,
    empresa_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Tabela editável de colaboradores — estilo planilha Excel."""
    empresas = listar_empresas_ativas(db)
    colaboradores = get_colaboradores_por_empresa(db, empresa_id, apenas_ativos=False) if empresa_id else []
    return colabs_templates.TemplateResponse("colaboradores_tabela.html", {
        "request": request,
        "empresas": empresas,
        "colaboradores": colaboradores,
        "empresa_id_selecionada": empresa_id,
    })


@colabs_router.post("/", response_class=JSONResponse)
async def adicionar_colaborador(
    empresa_id: int = Form(...),
    nome_completo: str = Form(...),
    cpf: str = Form(...),
    cargo: str = Form(...),
    setor: str = Form(""),
    data_admissao: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Insere novo colaborador (chamado via AJAX da tabela editável)."""
    if not validar_cpf(cpf):
        return JSONResponse({"ok": False, "erro": f"CPF inválido: {cpf}"}, status_code=400)

    data_adm = None
    if data_admissao:
        try:
            from datetime import datetime
            data_adm = datetime.strptime(data_admissao, "%Y-%m-%d").date()
        except ValueError:
            pass

    col = criar_colaborador(db, empresa_id, nome_completo, cpf, cargo, setor, data_adm)
    return JSONResponse({"ok": True, "id": col.id, "mensagem": f"Colaborador {nome_completo} cadastrado."})


@colabs_router.put("/{colaborador_id}", response_class=JSONResponse)
async def atualizar_colaborador(
    colaborador_id: int,
    nome_completo: str = Form(...),
    cargo: str = Form(...),
    setor: str = Form(""),
    db: Session = Depends(get_db),
):
    """Atualiza dados do colaborador inline (chamado via AJAX)."""
    col = db.get(Colaborador, colaborador_id)
    if not col:
        return JSONResponse({"ok": False, "erro": "Colaborador não encontrado"}, status_code=404)
    col.nome_completo = nome_completo.strip()
    col.cargo = cargo.strip()
    col.setor = setor.strip()
    db.commit()
    return JSONResponse({"ok": True, "mensagem": "Dados atualizados."})


@colabs_router.delete("/{colaborador_id}", response_class=JSONResponse)
async def demitir_colaborador(
    colaborador_id: int,
    data_demissao: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Inativa colaborador (demissional) sem excluir do banco."""
    data_dem = None
    if data_demissao:
        try:
            from datetime import datetime
            data_dem = datetime.strptime(data_demissao, "%Y-%m-%d").date()
        except ValueError:
            pass

    col = inativar_colaborador(db, colaborador_id, data_dem)
    return JSONResponse({
        "ok": True,
        "mensagem": f"Colaborador {col.nome_completo} inativado em {col.data_demissao}."
    })


# ---------------------------------------------------------------------------
# API — Buscar cargos disponíveis para uma empresa (usado no formulário)
# ---------------------------------------------------------------------------

@router.get("/api/cargos/{empresa_id}", response_class=JSONResponse)
async def api_cargos(empresa_id: int, db: Session = Depends(get_db)):
    cargos = listar_cargos_por_empresa(db, empresa_id)
    return JSONResponse({"cargos": cargos})


@router.get("/api/colaboradores/{empresa_id}", response_class=JSONResponse)
async def api_colaboradores(empresa_id: int, db: Session = Depends(get_db)):
    cols = get_colaboradores_por_empresa(db, empresa_id)
    return JSONResponse({
        "colaboradores": [
            {"id": c.id, "nome": c.nome_completo, "cpf": c.cpf, "cargo": c.cargo or ""}
            for c in cols
        ]
    })
