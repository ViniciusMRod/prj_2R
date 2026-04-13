"""Testes unitários — módulo de extração."""
import pytest
from src.extraction.validators import (
    formatar_cnpj, formatar_cpf, validar_cnpj, validar_cpf,
    validar_datas_exame, validar_periodicidade, validar_dados_extraidos,
)
from datetime import date


class TestValidarCNPJ:
    def test_cnpj_valido_formatado(self):
        assert validar_cnpj("11.222.333/0001-81") is True

    def test_cnpj_valido_sem_formatacao(self):
        assert validar_cnpj("11222333000181") is True

    def test_cnpj_invalido(self):
        assert validar_cnpj("12.345.678/0001-00") is False

    def test_cnpj_todos_iguais(self):
        assert validar_cnpj("11.111.111/1111-11") is False

    def test_cnpj_tamanho_errado(self):
        assert validar_cnpj("123") is False


class TestValidarCPF:
    def test_cpf_valido_formatado(self):
        assert validar_cpf("123.456.789-09") is True

    def test_cpf_valido_sem_formatacao(self):
        assert validar_cpf("12345678909") is True

    def test_cpf_invalido(self):
        assert validar_cpf("123.456.789-00") is False

    def test_cpf_todos_iguais(self):
        assert validar_cpf("111.111.111-11") is False

    def test_cpf_tamanho_errado(self):
        assert validar_cpf("123") is False


class TestFormatacao:
    def test_formatar_cnpj(self):
        assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_formatar_cpf(self):
        assert formatar_cpf("12345678909") == "123.456.789-09"


class TestValidarDatas:
    def test_datas_coerentes(self):
        ok, msg = validar_datas_exame(date(2024, 1, 1), date(2025, 1, 1))
        assert ok is True
        assert msg == ""

    def test_ultimo_maior_que_proximo(self):
        ok, msg = validar_datas_exame(date(2025, 6, 1), date(2025, 1, 1))
        assert ok is False
        assert "anterior" in msg

    def test_sem_ultimo_exame(self):
        ok, _ = validar_datas_exame(None, date(2025, 6, 1))
        assert ok is True


class TestPeriodicidade:
    def test_periodicidades_validas(self):
        for p in [6, 12, 24, 36, 48, 60]:
            ok, _ = validar_periodicidade(p)
            assert ok is True

    def test_periodicidade_invalida(self):
        ok, msg = validar_periodicidade(7)
        assert ok is False
        assert "7" in msg


class TestValidarDadosExtraidos:
    def _dados_validos(self):
        return {
            "empresa": {"cnpj": "11.222.333/0001-81", "razao_social": "Empresa Teste"},
            "colaboradores": [
                {"nome_completo": "João Silva", "cpf": "12345678909"},
            ],
            "exames": [
                {"tipo_exame": "Audiometria", "periodicidade_meses": 12},
            ],
        }

    def test_dados_validos(self):
        result = validar_dados_extraidos(self._dados_validos())
        assert result["valido"] is True
        assert result["erros"] == []

    def test_cnpj_faltando(self):
        dados = self._dados_validos()
        dados["empresa"]["cnpj"] = ""
        result = validar_dados_extraidos(dados)
        assert result["valido"] is False

    def test_cpf_invalido_detectado(self):
        dados = self._dados_validos()
        dados["colaboradores"][0]["cpf"] = "00000000000"
        result = validar_dados_extraidos(dados)
        assert len(result["colaboradores_invalidos"]) > 0

    def test_sem_colaboradores(self):
        dados = self._dados_validos()
        dados["colaboradores"] = []
        result = validar_dados_extraidos(dados)
        assert result["valido"] is False
