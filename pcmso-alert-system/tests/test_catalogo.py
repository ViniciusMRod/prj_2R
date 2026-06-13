"""Testes da normalização do catálogo de exames (Fase 2, item 1)."""
from src.extraction.catalogo import _chave, _limpar, normalizar_exame


def test_limpar_junta_quebra_de_linha():
    assert _limpar("ECG Convencional de até 12 Derivações\n(+40 anos)") == \
        "ECG Convencional de até 12 Derivações (+40 anos)"


def test_limpar_remove_dois_pontos_e_espacos():
    assert _limpar("  Exame Clinico:  ") == "Exame Clinico"


def test_chave_ignora_caixa_e_acento():
    assert _chave("Acuidade Visual") == _chave("Acuidade visual") == "acuidade visual"
    assert _chave("Audiometria Tonal") == _chave("Audiometria tonal")


def test_chave_converge_quebra_de_linha():
    a = _chave("Hemograma Completo com contagem de\nPlaquetas")
    b = _chave("hemograma completo com contagem de plaquetas")
    assert a == b


def test_normalizar_usa_grafia_preferida_dos_sinonimos():
    # ambas as grafias caem no mesmo display preferido e na mesma chave
    disp1, k1 = normalizar_exame("Acuidade visual")
    disp2, k2 = normalizar_exame("Acuidade Visual")
    assert disp1 == disp2 == "Acuidade Visual"
    assert k1 == k2 == "acuidade visual"


def test_normalizar_sem_sinonimo_mantem_nome_limpo():
    disp, chave = normalizar_exame("Glicemia ")
    assert disp == "Glicemia"
    assert chave == "glicemia"


def test_normalizar_vazio():
    assert normalizar_exame("") == ("", "")
    assert normalizar_exame(None) == ("", "")
