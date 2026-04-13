"""
Gerenciador de demandas de movimentações de colaboradores.
Consulta o mapeamento cargo → exames e gera os registros automaticamente.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import (
    Colaborador,
    Demanda,
    Exame,
    StatusDemanda,
    StatusExame,
    TipoMovimentacao,
)
from src.database.queries import get_exames_por_cargo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cálculo de prazos por tipo de movimentação
# ---------------------------------------------------------------------------

PRAZOS_MOVIMENTACAO: dict[TipoMovimentacao, int] = {
    TipoMovimentacao.ADMISSIONAL: 7,       # até D+7
    TipoMovimentacao.PERIODICO: 30,        # até D+30
    TipoMovimentacao.DEMISSIONAL: 3,       # até D+3
    TipoMovimentacao.RETORNO: 1,           # até D+1
    TipoMovimentacao.MUDANCA_FUNCAO: 15,   # até D+15
}


def calcular_prazo(tipo_movimentacao: TipoMovimentacao, data_base: Optional[date] = None) -> date:
    """
    Calcula a data limite para realização dos exames conforme o tipo de movimentação.
    """
    base = data_base or date.today()
    dias = PRAZOS_MOVIMENTACAO.get(tipo_movimentacao, 30)
    return base + timedelta(days=dias)


def calcular_data_proximo_exame(
    tipo_movimentacao: TipoMovimentacao,
    periodicidade_meses: int,
    data_base: Optional[date] = None,
) -> date:
    """
    Calcula data_proximo_exame com base no tipo de movimentação:
    - Admissional/demissional/retorno: data atual (exame imediato)
    - Periódico: data_base + periodicidade
    - Mudança de função: data atual
    """
    base = data_base or date.today()

    if tipo_movimentacao in (
        TipoMovimentacao.ADMISSIONAL,
        TipoMovimentacao.DEMISSIONAL,
        TipoMovimentacao.RETORNO,
        TipoMovimentacao.MUDANCA_FUNCAO,
    ):
        return base  # exame deve ser feito agora

    # Periódico: próximo exame após a periodicidade
    from dateutil.relativedelta import relativedelta
    return base + relativedelta(months=periodicidade_meses)


# ---------------------------------------------------------------------------
# Criação de colaborador (admissional)
# ---------------------------------------------------------------------------

def criar_colaborador(
    db: Session,
    empresa_id: int,
    nome_completo: str,
    cpf: str,
    cargo: str,
    setor: str = "",
    data_admissao: Optional[date] = None,
) -> Colaborador:
    """
    Cria um novo colaborador no banco (fluxo admissional).
    CPF deve ser fornecido sem formatação ou com formatação padrão.
    """
    import re
    cpf_limpo = re.sub(r"[^\d]", "", cpf)
    # Formatar no padrão XXX.XXX.XXX-XX
    cpf_fmt = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(cpf_limpo) == 11 else cpf

    colaborador = Colaborador(
        empresa_id=empresa_id,
        nome_completo=nome_completo.strip(),
        cpf=cpf_fmt,
        cargo=cargo.strip(),
        setor=setor.strip(),
        data_admissao=data_admissao or date.today(),
        ativo=True,
    )
    db.add(colaborador)
    db.flush()  # para obter o ID sem commit ainda
    logger.info(f"Colaborador criado: {nome_completo} CPF={cpf_fmt} empresa_id={empresa_id}")
    return colaborador


def inativar_colaborador(
    db: Session,
    colaborador_id: int,
    data_demissao: Optional[date] = None,
) -> Colaborador:
    """Inativa um colaborador (fluxo demissional). Não exclui o registro."""
    colaborador = db.get(Colaborador, colaborador_id)
    if not colaborador:
        raise ValueError(f"Colaborador id={colaborador_id} não encontrado.")
    colaborador.ativo = False
    colaborador.data_demissao = data_demissao or date.today()
    db.flush()
    logger.info(f"Colaborador inativado: id={colaborador_id} demissão={colaborador.data_demissao}")
    return colaborador


# ---------------------------------------------------------------------------
# Geração automática de demanda + exames
# ---------------------------------------------------------------------------

def gerar_demanda(
    db: Session,
    empresa_id: int,
    colaborador_id: int,
    cargo: str,
    tipo_movimentacao: TipoMovimentacao,
    tecnico_responsavel: str = "",
    observacoes: str = "",
) -> dict:
    """
    Cria uma demanda e gera automaticamente os exames obrigatórios
    com base no mapeamento cargo_exames da empresa.

    Retorna:
    {
        "demanda": Demanda,
        "exames_criados": [Exame],
        "exames_sem_mapeamento": bool,
        "mensagem": str
    }
    """
    # 1. Buscar exames obrigatórios para o cargo
    cargo_exames = get_exames_por_cargo(db, empresa_id, cargo)

    exames_criados: list[Exame] = []
    exames_snapshot: list[dict] = []

    prazo = calcular_prazo(tipo_movimentacao)

    # 2. Criar registro de exame para cada exame obrigatório
    for ce in cargo_exames:
        tipo_exame = ce.tipo_exame
        periodicidade = ce.periodicidade_meses or tipo_exame.periodicidade_meses

        data_proximo = calcular_data_proximo_exame(tipo_movimentacao, periodicidade)

        exame = Exame(
            colaborador_id=colaborador_id,
            tipo_exame_id=tipo_exame.id,
            data_proximo_exame=data_proximo,
            status=StatusExame.PENDENTE,
            observacoes=f"Gerado via demanda {tipo_movimentacao.value}",
        )
        db.add(exame)
        db.flush()
        exames_criados.append(exame)

        exames_snapshot.append({
            "exame_id": exame.id,
            "tipo_exame": tipo_exame.nome,
            "data_proximo_exame": data_proximo.isoformat(),
            "periodicidade_meses": periodicidade,
        })

    # 3. Criar a demanda
    demanda = Demanda(
        empresa_id=empresa_id,
        colaborador_id=colaborador_id,
        cargo=cargo,
        tipo_movimentacao=tipo_movimentacao,
        status=StatusDemanda.PENDENTE,
        exames_gerados=exames_snapshot,
        tecnico_responsavel=tecnico_responsavel,
        observacoes=observacoes,
        data_prazo=prazo,
    )
    db.add(demanda)
    db.commit()
    db.refresh(demanda)

    sem_mapeamento = len(cargo_exames) == 0

    mensagem = (
        f"Demanda criada: {len(exames_criados)} exame(s) gerado(s) para cargo '{cargo}' "
        f"({tipo_movimentacao.value}), prazo: {prazo.strftime('%d/%m/%Y')}."
        if not sem_mapeamento
        else f"ATENÇÃO: nenhum exame encontrado para o cargo '{cargo}' na empresa. "
             f"Verifique o mapeamento cargo-exames ou adicione manualmente."
    )

    logger.info(mensagem)

    return {
        "demanda": demanda,
        "exames_criados": exames_criados,
        "exames_sem_mapeamento": sem_mapeamento,
        "mensagem": mensagem,
    }
