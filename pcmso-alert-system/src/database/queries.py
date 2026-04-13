"""
Queries reutilizáveis para o PCMSO Alert System.
Todas as funções recebem uma SQLAlchemy Session como parâmetro.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from src.database.models import (
    AlertaEnviado,
    CanalAlerta,
    CargoExame,
    Colaborador,
    Demanda,
    Empresa,
    Exame,
    StatusEnvio,
    StatusExame,
    TipoExame,
    ValidacaoPendente,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

def get_empresa_by_id(db: Session, empresa_id: int) -> Optional[Empresa]:
    return db.get(Empresa, empresa_id)


def get_empresa_by_cnpj(db: Session, cnpj: str) -> Optional[Empresa]:
    return db.scalar(select(Empresa).where(Empresa.cnpj == cnpj))


def listar_empresas_ativas(db: Session) -> list[Empresa]:
    return list(db.scalars(select(Empresa).where(Empresa.ativo == True).order_by(Empresa.razao_social)))


# ---------------------------------------------------------------------------
# Colaboradores
# ---------------------------------------------------------------------------

def get_colaboradores_por_empresa(db: Session, empresa_id: int, apenas_ativos: bool = True) -> list[Colaborador]:
    q = select(Colaborador).where(Colaborador.empresa_id == empresa_id)
    if apenas_ativos:
        q = q.where(Colaborador.ativo == True)
    return list(db.scalars(q.order_by(Colaborador.nome_completo)))


def get_colaborador_by_cpf(db: Session, cpf: str) -> Optional[Colaborador]:
    cpf_limpo = cpf.replace(".", "").replace("-", "")
    return db.scalar(select(Colaborador).where(
        func.regexp_replace(Colaborador.cpf, r"[\.\-]", "", "g") == cpf_limpo
    ))


# ---------------------------------------------------------------------------
# Exames — Motor de Alertas
# ---------------------------------------------------------------------------

def query_exames_por_vencimento(db: Session, data_inicio: date, data_fim: date) -> list[Exame]:
    """
    Retorna exames com data_proximo_exame dentro da janela [data_inicio, data_fim].
    Inclui colaborador e empresa via joinedload para evitar N+1.
    """
    return list(db.scalars(
        select(Exame)
        .options(
            joinedload(Exame.colaborador).joinedload(Colaborador.empresa),
            joinedload(Exame.tipo_exame),
        )
        .where(
            and_(
                Exame.data_proximo_exame >= data_inicio,
                Exame.data_proximo_exame <= data_fim,
                Exame.status.in_([StatusExame.PENDENTE, StatusExame.AGENDADO]),
            )
        )
        .order_by(Exame.data_proximo_exame)
    ))


def agrupar_por_empresa(exames: list[Exame]) -> dict[int, list[Exame]]:
    """Agrupa lista de exames por empresa_id."""
    grupos: dict[int, list[Exame]] = {}
    for exame in exames:
        eid = exame.colaborador.empresa_id
        grupos.setdefault(eid, []).append(exame)
    return grupos


def alerta_ja_enviado_hoje(db: Session, empresa_id: int, canal: CanalAlerta) -> bool:
    """Verifica se já foi enviado alerta para esta empresa hoje neste canal."""
    hoje = date.today()
    count = db.scalar(
        select(func.count(AlertaEnviado.id)).where(
            and_(
                AlertaEnviado.empresa_id == empresa_id,
                AlertaEnviado.canal == canal,
                AlertaEnviado.status_envio == StatusEnvio.ENVIADO,
                func.date(AlertaEnviado.data_envio) == hoje,
            )
        )
    )
    return (count or 0) > 0


def marcar_exames_vencidos(db: Session) -> int:
    """
    Atualiza para VENCIDO todos os exames pendentes com data_proximo_exame < hoje.
    Retorna quantidade de registros atualizados.
    """
    from sqlalchemy import update
    hoje = date.today()
    result = db.execute(
        update(Exame)
        .where(
            and_(
                Exame.data_proximo_exame < hoje,
                Exame.status == StatusExame.PENDENTE,
            )
        )
        .values(status=StatusExame.VENCIDO)
    )
    db.commit()
    count = result.rowcount
    if count:
        logger.info(f"{count} exame(s) marcado(s) como VENCIDO.")
    return count


# ---------------------------------------------------------------------------
# Cargo × Exames
# ---------------------------------------------------------------------------

def get_exames_por_cargo(db: Session, empresa_id: int, cargo: str) -> list[CargoExame]:
    """Retorna os exames obrigatórios para um cargo em uma empresa."""
    return list(db.scalars(
        select(CargoExame)
        .options(joinedload(CargoExame.tipo_exame))
        .where(
            and_(
                CargoExame.empresa_id == empresa_id,
                func.lower(CargoExame.cargo) == cargo.lower(),
                CargoExame.obrigatorio == True,
            )
        )
    ))


def listar_cargos_por_empresa(db: Session, empresa_id: int) -> list[str]:
    """Lista cargos únicos cadastrados para uma empresa."""
    result = db.scalars(
        select(CargoExame.cargo)
        .where(CargoExame.empresa_id == empresa_id)
        .distinct()
        .order_by(CargoExame.cargo)
    )
    return list(result)


# ---------------------------------------------------------------------------
# Demandas
# ---------------------------------------------------------------------------

def get_demandas_ativas(db: Session, empresa_id: Optional[int] = None) -> list[Demanda]:
    from src.database.models import StatusDemanda
    q = (
        select(Demanda)
        .options(
            joinedload(Demanda.colaborador),
            joinedload(Demanda.empresa),
        )
        .where(Demanda.status.in_([StatusDemanda.PENDENTE, StatusDemanda.AGENDADO]))
        .order_by(Demanda.data_prazo.asc().nulls_last(), Demanda.created_at.desc())
    )
    if empresa_id:
        q = q.where(Demanda.empresa_id == empresa_id)
    return list(db.scalars(q))


# ---------------------------------------------------------------------------
# Validação Pendente
# ---------------------------------------------------------------------------

def get_validacoes_pendentes(db: Session) -> list[ValidacaoPendente]:
    from src.database.models import StatusValidacao
    return list(db.scalars(
        select(ValidacaoPendente)
        .options(joinedload(ValidacaoPendente.empresa))
        .where(ValidacaoPendente.status == StatusValidacao.PENDENTE)
        .order_by(ValidacaoPendente.data_upload.desc())
    ))


# ---------------------------------------------------------------------------
# Dashboard — métricas
# ---------------------------------------------------------------------------

def get_metricas_empresa(db: Session, empresa_id: int) -> dict:
    """Retorna KPIs para o dashboard de uma empresa."""
    hoje = date.today()
    janela_90 = hoje + timedelta(days=90)

    total_colaboradores = db.scalar(
        select(func.count(Colaborador.id)).where(
            and_(Colaborador.empresa_id == empresa_id, Colaborador.ativo == True)
        )
    ) or 0

    total_exames = db.scalar(
        select(func.count(Exame.id))
        .join(Colaborador)
        .where(Colaborador.empresa_id == empresa_id)
    ) or 0

    em_dia = db.scalar(
        select(func.count(Exame.id))
        .join(Colaborador)
        .where(
            and_(
                Colaborador.empresa_id == empresa_id,
                Exame.status == StatusExame.REALIZADO,
            )
        )
    ) or 0

    vencidos = db.scalar(
        select(func.count(Exame.id))
        .join(Colaborador)
        .where(
            and_(
                Colaborador.empresa_id == empresa_id,
                Exame.status == StatusExame.VENCIDO,
            )
        )
    ) or 0

    proximos_90d = db.scalar(
        select(func.count(Exame.id))
        .join(Colaborador)
        .where(
            and_(
                Colaborador.empresa_id == empresa_id,
                Exame.data_proximo_exame >= hoje,
                Exame.data_proximo_exame <= janela_90,
                Exame.status.in_([StatusExame.PENDENTE, StatusExame.AGENDADO]),
            )
        )
    ) or 0

    return {
        "total_colaboradores": total_colaboradores,
        "total_exames": total_exames,
        "em_dia": em_dia,
        "vencidos": vencidos,
        "proximos_90_dias": proximos_90d,
    }
