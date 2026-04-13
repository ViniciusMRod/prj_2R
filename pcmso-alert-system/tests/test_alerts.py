"""Testes unitários — motor de alertas."""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.business_logic.alert_engine import JANELA_FIM_DIAS, JANELA_INICIO_DIAS
from src.demandas.demand_manager import calcular_prazo, calcular_data_proximo_exame
from src.database.models import TipoMovimentacao


class TestJanelaAlertas:
    def test_janela_10_15_dias(self):
        hoje = date.today()
        assert JANELA_INICIO_DIAS == 10
        assert JANELA_FIM_DIAS == 15

    def test_janela_calculada(self):
        hoje = date.today()
        inicio = hoje + timedelta(days=JANELA_INICIO_DIAS)
        fim    = hoje + timedelta(days=JANELA_FIM_DIAS)
        assert (fim - inicio).days == 5


class TestCalculoPrazos:
    def test_prazo_admissional(self):
        base = date(2026, 4, 8)
        prazo = calcular_prazo(TipoMovimentacao.ADMISSIONAL, base)
        assert prazo == base + timedelta(days=7)

    def test_prazo_periodico(self):
        base = date(2026, 4, 8)
        prazo = calcular_prazo(TipoMovimentacao.PERIODICO, base)
        assert prazo == base + timedelta(days=30)

    def test_prazo_demissional(self):
        base = date(2026, 4, 8)
        prazo = calcular_prazo(TipoMovimentacao.DEMISSIONAL, base)
        assert prazo == base + timedelta(days=3)

    def test_prazo_retorno(self):
        base = date(2026, 4, 8)
        prazo = calcular_prazo(TipoMovimentacao.RETORNO, base)
        assert prazo == base + timedelta(days=1)


class TestDataProximoExame:
    def test_admissional_data_imediata(self):
        base = date(2026, 4, 8)
        data = calcular_data_proximo_exame(TipoMovimentacao.ADMISSIONAL, 12, base)
        assert data == base

    def test_demissional_data_imediata(self):
        base = date(2026, 4, 8)
        data = calcular_data_proximo_exame(TipoMovimentacao.DEMISSIONAL, 12, base)
        assert data == base

    def test_periodico_soma_meses(self):
        from dateutil.relativedelta import relativedelta
        base = date(2026, 4, 8)
        data = calcular_data_proximo_exame(TipoMovimentacao.PERIODICO, 12, base)
        assert data == base + relativedelta(months=12)


class TestAgruparPorEmpresa:
    def test_agrupamento(self):
        from src.database.queries import agrupar_por_empresa

        def make_exame(empresa_id):
            ex = MagicMock()
            ex.colaborador.empresa_id = empresa_id
            return ex

        exames = [make_exame(1), make_exame(1), make_exame(2), make_exame(2), make_exame(2)]
        grupos = agrupar_por_empresa(exames)

        assert len(grupos) == 2
        assert len(grupos[1]) == 2
        assert len(grupos[2]) == 3
