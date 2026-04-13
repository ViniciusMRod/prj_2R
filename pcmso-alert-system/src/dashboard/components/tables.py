"""
Componentes de tabelas para o dashboard Streamlit.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.database.models import Colaborador, Exame, StatusExame, TipoExame


def tabela_colaboradores(db: Session, empresa_id: int) -> None:
    """Exibe tabela filtrável de colaboradores com status de exames."""
    cols = db.execute(
        select(
            Colaborador.id,
            Colaborador.nome_completo,
            Colaborador.cpf,
            Colaborador.cargo,
            Colaborador.setor,
            Colaborador.data_admissao,
        )
        .where(and_(Colaborador.empresa_id == empresa_id, Colaborador.ativo == True))
        .order_by(Colaborador.nome_completo)
    ).fetchall()

    if not cols:
        st.info("Nenhum colaborador ativo encontrado.")
        return

    df = pd.DataFrame(cols, columns=["ID", "Nome", "CPF", "Cargo", "Setor", "Admissão"])

    # Filtros
    c1, c2 = st.columns(2)
    filtro_nome  = c1.text_input("Filtrar por nome", "")
    filtro_cargo = c2.text_input("Filtrar por cargo", "")

    if filtro_nome:
        df = df[df["Nome"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_cargo:
        df = df[df["Cargo"].str.contains(filtro_cargo, case=False, na=False)]

    st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} colaborador(es) exibido(s)")


def tabela_exames(db: Session, empresa_id: int) -> None:
    """Exibe tabela de exames com filtros por status, tipo e período."""
    from datetime import date, timedelta

    rows = db.execute(
        select(
            Colaborador.nome_completo,
            TipoExame.nome.label("tipo_exame"),
            Exame.data_ultimo_exame,
            Exame.data_proximo_exame,
            Exame.status,
        )
        .join(Colaborador, Exame.colaborador_id == Colaborador.id)
        .join(TipoExame, Exame.tipo_exame_id == TipoExame.id)
        .where(Colaborador.empresa_id == empresa_id)
        .order_by(Exame.data_proximo_exame)
    ).fetchall()

    if not rows:
        st.info("Nenhum exame cadastrado.")
        return

    df = pd.DataFrame(rows, columns=["Colaborador", "Tipo Exame", "Último Exame", "Próximo Exame", "Status"])

    # Filtros
    c1, c2, c3 = st.columns(3)
    status_opcoes = ["Todos"] + [s.value for s in StatusExame]
    filtro_status = c1.selectbox("Status", status_opcoes)
    filtro_tipo   = c2.text_input("Tipo de exame", "")
    filtro_dias   = c3.slider("Vencendo em (dias)", 0, 180, 90)

    if filtro_status != "Todos":
        df = df[df["Status"] == filtro_status]
    if filtro_tipo:
        df = df[df["Tipo Exame"].str.contains(filtro_tipo, case=False, na=False)]

    hoje = date.today()
    limite = hoje + timedelta(days=filtro_dias)
    df["Próximo Exame"] = pd.to_datetime(df["Próximo Exame"])
    df = df[df["Próximo Exame"].dt.date <= limite]

    # Colorir por urgência
    def cor_status(status: str) -> str:
        return {"vencido": "background-color:#fde8e8",
                "pendente": "background-color:#fef9e7"}.get(status, "")

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} exame(s) exibido(s)")
