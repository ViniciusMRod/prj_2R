"""
Dashboard Streamlit — PCMSO Alert System.
Interface multi-página para empresas clientes visualizarem seus dados.
"""
from __future__ import annotations

import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="PCMSO Alert System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Injetar CSS
st.markdown("""
<style>
    .metric-card {
        background: white;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,.08);
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; }
    .metric-label { color: #666; font-size: 0.85rem; margin-top: 4px; }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Autenticação simples por CNPJ + senha
# ---------------------------------------------------------------------------

def tela_login() -> None:
    st.title("🛡️ PCMSO Alert System")
    st.subheader("Acesso ao Dashboard")

    with st.form("login_form"):
        cnpj  = st.text_input("CNPJ da Empresa", placeholder="00.000.000/0000-00")
        senha = st.text_input("Senha", type="password")
        btn   = st.form_submit_button("Entrar", use_container_width=True)

    if btn:
        if not cnpj or not senha:
            st.error("Preencha o CNPJ e a senha.")
            return

        from config.database import get_db_context
        from src.database.queries import get_empresa_by_cnpj
        import bcrypt

        with get_db_context() as db:
            empresa = get_empresa_by_cnpj(db, cnpj)

        if not empresa or not empresa.senha_dashboard:
            st.error("CNPJ não encontrado ou sem acesso ao dashboard.")
            return

        try:
            senha_ok = bcrypt.checkpw(senha.encode(), empresa.senha_dashboard.encode())
        except Exception:
            senha_ok = (senha == empresa.senha_dashboard)  # fallback para testes

        if senha_ok:
            st.session_state["empresa_id"]    = empresa.id
            st.session_state["empresa_nome"]  = empresa.razao_social
            st.session_state["empresa_cnpj"]  = empresa.cnpj
            st.session_state["autenticado"]   = True
            st.rerun()
        else:
            st.error("Senha incorreta.")


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

def dashboard_principal() -> None:
    empresa_id   = st.session_state["empresa_id"]
    empresa_nome = st.session_state["empresa_nome"]

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 🏢 {empresa_nome}")
        st.markdown(f"*{st.session_state['empresa_cnpj']}*")
        st.divider()

        pagina = st.radio(
            "Navegação",
            ["📊 Visão Geral", "👥 Colaboradores", "🔬 Exames", "📋 Relatórios"],
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            for key in ["empresa_id", "empresa_nome", "empresa_cnpj", "autenticado"]:
                st.session_state.pop(key, None)
            st.rerun()

    # Conteúdo por página
    if pagina == "📊 Visão Geral":
        pagina_visao_geral(empresa_id, empresa_nome)
    elif pagina == "👥 Colaboradores":
        pagina_colaboradores(empresa_id)
    elif pagina == "🔬 Exames":
        pagina_exames(empresa_id)
    elif pagina == "📋 Relatórios":
        pagina_relatorios(empresa_id, empresa_nome)


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

def pagina_visao_geral(empresa_id: int, empresa_nome: str) -> None:
    st.title(f"📊 Visão Geral — {empresa_nome}")
    st.caption(f"Atualizado em: {date.today().strftime('%d/%m/%Y')}")

    from config.database import get_db_context
    from src.database.queries import get_metricas_empresa
    from src.dashboard.components.charts import grafico_status_pizza, grafico_vencimentos_90_dias

    with get_db_context() as db:
        metricas = get_metricas_empresa(db, empresa_id)

    # KPIs
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("👥 Colaboradores", metricas["total_colaboradores"])
    with c2:
        st.metric("✅ Em Dia", metricas["em_dia"])
    with c3:
        st.metric("⏰ Próx. 90 dias", metricas["proximos_90_dias"], delta=None)
    with c4:
        st.metric("❌ Vencidos", metricas["vencidos"],
                  delta=f"-{metricas['vencidos']}" if metricas["vencidos"] > 0 else None,
                  delta_color="inverse")
    with c5:
        total = metricas["total_exames"] or 1
        pct_ok = round(metricas["em_dia"] / total * 100)
        st.metric("📈 Conformidade", f"{pct_ok}%")

    st.divider()

    # Gráficos
    col_left, col_right = st.columns([2, 1])
    with col_left:
        with get_db_context() as db:
            fig_bar = grafico_vencimentos_90_dias(db, empresa_id)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_right:
        fig_pizza = grafico_status_pizza(metricas)
        st.plotly_chart(fig_pizza, use_container_width=True)


def pagina_colaboradores(empresa_id: int) -> None:
    st.title("👥 Colaboradores")

    from config.database import get_db_context
    from src.dashboard.components.tables import tabela_colaboradores

    with get_db_context() as db:
        tabela_colaboradores(db, empresa_id)


def pagina_exames(empresa_id: int) -> None:
    st.title("🔬 Exames Ocupacionais")

    from config.database import get_db_context
    from src.dashboard.components.tables import tabela_exames

    with get_db_context() as db:
        tabela_exames(db, empresa_id)


def pagina_relatorios(empresa_id: int, empresa_nome: str) -> None:
    st.title("📋 Relatórios")

    tab1, tab2 = st.tabs(["📥 Exportar Dados", "📨 Histórico de Alertas"])

    with tab1:
        st.subheader("Exportar para Excel")
        col1, col2 = st.columns(2)
        mes = col1.selectbox("Mês", range(1, 13), index=date.today().month - 1,
                             format_func=lambda m: [
                                 "Jan","Fev","Mar","Abr","Mai","Jun",
                                 "Jul","Ago","Set","Out","Nov","Dez"
                             ][m-1])
        ano = col2.number_input("Ano", min_value=2020, max_value=2099, value=date.today().year)

        if st.button("📊 Gerar Relatório", use_container_width=True):
            from config.database import get_db_context
            from src.business_logic.report_builder import (
                _get_dados_empresa_mes, gerar_excel_empresa, gerar_pdf_empresa,
            )
            from src.database.queries import get_empresa_by_id

            with get_db_context() as db:
                empresa = get_empresa_by_id(db, empresa_id)
                dados   = _get_dados_empresa_mes(db, empresa_id, int(ano), int(mes))

            xlsx_path = gerar_excel_empresa(empresa, dados, int(ano), int(mes))
            pdf_path  = gerar_pdf_empresa(empresa, dados, int(ano), int(mes))

            if xlsx_path and os.path.exists(xlsx_path):
                with open(xlsx_path, "rb") as f:
                    st.download_button("⬇️ Baixar Excel", f.read(),
                                       file_name=os.path.basename(xlsx_path),
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button("⬇️ Baixar PDF", f.read(),
                                       file_name=os.path.basename(pdf_path),
                                       mime="application/pdf")

    with tab2:
        st.subheader("Alertas Recebidos")
        from config.database import get_db_context
        from sqlalchemy import select, desc
        from src.database.models import AlertaEnviado, StatusEnvio

        with get_db_context() as db:
            alertas = db.execute(
                select(
                    AlertaEnviado.data_envio,
                    AlertaEnviado.canal,
                    AlertaEnviado.status_envio,
                )
                .where(AlertaEnviado.empresa_id == empresa_id)
                .order_by(desc(AlertaEnviado.data_envio))
                .limit(50)
            ).fetchall()

        if not alertas:
            st.info("Nenhum alerta registrado ainda.")
        else:
            import pandas as pd
            df = pd.DataFrame(alertas, columns=["Data/Hora", "Canal", "Status"])
            df["Data/Hora"] = pd.to_datetime(df["Data/Hora"]).dt.strftime("%d/%m/%Y %H:%M")
            st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if not st.session_state.get("autenticado"):
    tela_login()
else:
    dashboard_principal()
