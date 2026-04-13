"""
Componentes de gráficos para o dashboard Streamlit.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from src.database.models import Colaborador, Exame, StatusExame


def grafico_vencimentos_90_dias(db: Session, empresa_id: int) -> go.Figure:
    """Gráfico de barras com exames vencendo nos próximos 90 dias (agrupado por semana)."""
    hoje = date.today()
    fim  = hoje + timedelta(days=90)

    rows = db.execute(
        select(Exame.data_proximo_exame, func.count(Exame.id).label("qtd"))
        .join(Colaborador)
        .where(
            and_(
                Colaborador.empresa_id == empresa_id,
                Exame.data_proximo_exame >= hoje,
                Exame.data_proximo_exame <= fim,
                Exame.status.in_([StatusExame.PENDENTE, StatusExame.AGENDADO]),
            )
        )
        .group_by(Exame.data_proximo_exame)
        .order_by(Exame.data_proximo_exame)
    ).fetchall()

    if not rows:
        fig = go.Figure()
        fig.add_annotation(text="Nenhum exame nos próximos 90 dias",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=300)
        return fig

    df = pd.DataFrame(rows, columns=["data", "qtd"])
    df["semana"] = pd.to_datetime(df["data"]).dt.to_period("W").apply(lambda r: r.start_time.date())
    df_sem = df.groupby("semana")["qtd"].sum().reset_index()
    df_sem.columns = ["Semana", "Exames"]

    # Colorir barras urgentes (primeiras 2 semanas)
    cores = ["#e74c3c" if (row["Semana"] - hoje).days <= 15 else "#3498db"
             for _, row in df_sem.iterrows()]

    fig = go.Figure(go.Bar(
        x=df_sem["Semana"].astype(str),
        y=df_sem["Exames"],
        marker_color=cores,
        text=df_sem["Exames"],
        textposition="outside",
    ))
    fig.update_layout(
        title="Exames por Semana — Próximos 90 Dias",
        xaxis_title="Semana",
        yaxis_title="Quantidade",
        height=350,
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    return fig


def grafico_status_pizza(metricas: dict) -> go.Figure:
    """Pizza com distribuição de status dos exames."""
    labels = ["Em Dia", "Pendentes", "Vencidos"]
    values = [
        metricas.get("em_dia", 0),
        metricas.get("proximos_90_dias", 0),
        metricas.get("vencidos", 0),
    ]
    cores = ["#27ae60", "#f39c12", "#e74c3c"]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=cores,
        hole=0.4,
        textinfo="label+percent+value",
    ))
    fig.update_layout(
        title="Status dos Exames",
        height=320,
        showlegend=True,
    )
    return fig
