"""Testes do parser das tabelas CONTROLE MÉDICO – CARGOS (cargo×exame)."""
from src.extraction.pdf_extractor import (
    _RE_CONTROLE_MEDICO,
    _parse_tabela_controle_medico,
    _tabela_parece_controle_medico,
)

TABELA_COM_TITULO = [
    ["CONTROLE MÉDICO – CARGOS: OFFICE BOY", None, None],
    ["Exame Clinico:", "Fazer no Admissional\nFazer no Periódico", "O periódico será feito a cada 12 meses"],
    ["Hemograma Completo e Plaquetas:", "Fazer no Admissional\nFazer no Demissional", "Este exame deverá ser feito a cada 6 meses"],
    ["*Nos casos de mudança de riscos ocupacionais", None, None],
]

# Variante em que o pdfplumber separa o título do corpo da tabela
TABELA_SEM_TITULO = TABELA_COM_TITULO[1:3]


def test_parse_tabela_com_titulo_embutido():
    entradas = _parse_tabela_controle_medico(TABELA_COM_TITULO, "OFFICE BOY")
    assert len(entradas) == 2  # título e rodapé (*) ignorados
    assert entradas[0]["cargo"] == "OFFICE BOY"
    assert entradas[0]["tipo_exame"] == "Exame Clinico"
    assert entradas[0]["periodicidade_meses"] == 12
    assert entradas[1]["tipo_exame"] == "Hemograma Completo e Plaquetas"
    assert entradas[1]["periodicidade_meses"] == 6


def test_momentos_extraidos():
    entradas = _parse_tabela_controle_medico(TABELA_COM_TITULO, "X")
    assert entradas[0]["momentos"] == ["Admissional", "Periódico"]
    assert entradas[1]["momentos"] == ["Admissional", "Demissional"]


def test_regex_titulo_extrai_cargo():
    m = _RE_CONTROLE_MEDICO.search("CONTROLE MÉDICO – CARGOS: GERENTE DE VENDAS")
    assert m and m.group(1).strip() == "GERENTE DE VENDAS"


def test_heuristica_tabela_sem_titulo():
    assert _tabela_parece_controle_medico(TABELA_SEM_TITULO)
    assert not _tabela_parece_controle_medico([["UNIDADE", "TELEFONE"], ["SAMU", "192"]])
