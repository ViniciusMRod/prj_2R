"""Testes do score de confiança da extração de PCMSO."""
import pytest

from src.extraction.pdf_extractor import calcular_confianca

TEXTO_PADRAO = """
01 – DADOS
Razão Social: EMPRESA TESTE LTDA
QUADRO DE CARGOS
"""

RESULTADO_COMPLETO = {
    "empresa": {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "12.345.678/0001-90",
        "vigencia_inicio": "01/2026",
        "vigencia_fim": "01/2027",
        "email_sso": "sso@empresa.com",
    },
    "cargos": [{"setor": "ADM", "cargo": "GERENTE", "quantidade": "1"}],
    "cargo_exames": [{"cargo": "GERENTE", "tipo_exame": "Audiometria"}],
}


def test_extracao_completa_nivel_alta():
    conf = calcular_confianca(RESULTADO_COMPLETO, TEXTO_PADRAO)
    assert conf["nivel"] == "ALTA"
    assert conf["score_geral"] >= 0.8
    assert conf["avisos"] == []


def test_sem_cnpj_e_vigencia_derruba_score():
    resultado = {
        **RESULTADO_COMPLETO,
        "empresa": {**RESULTADO_COMPLETO["empresa"], "cnpj": "", "vigencia_inicio": "", "vigencia_fim": ""},
    }
    conf = calcular_confianca(resultado, TEXTO_PADRAO)
    assert conf["nivel"] in ("MEDIA", "BAIXA")
    assert any("cnpj" in a for a in conf["avisos"])
    assert any("vigencia_fim" in a for a in conf["avisos"])


def test_layout_fora_do_padrao_gera_aviso():
    conf = calcular_confianca(RESULTADO_COMPLETO, "documento sem as seções esperadas")
    assert any("01 – DADOS" in a for a in conf["avisos"])
    assert any("QUADRO DE CARGOS" in a for a in conf["avisos"])
    assert conf["score_estrutura"] < 1


def test_extracao_vazia_nivel_baixa():
    resultado = {"empresa": {}, "cargos": [], "cargo_exames": []}
    conf = calcular_confianca(resultado, "")
    assert conf["nivel"] == "BAIXA"
    assert conf["score_geral"] < 0.5


def test_cnpj_formato_invalido_gera_aviso():
    resultado = {
        **RESULTADO_COMPLETO,
        "empresa": {**RESULTADO_COMPLETO["empresa"], "cnpj": "12345678000190"},
    }
    conf = calcular_confianca(resultado, TEXTO_PADRAO)
    assert any("formato inesperado" in a for a in conf["avisos"])
