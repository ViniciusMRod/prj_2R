"""Pré-checagem de versionamento no /extrair-lote (_classificar_versionamento).
Testa o mapeamento de ResultadoDuplicata → status_pcmso/mensagem_versao,
isolando a checagem de banco com monkeypatch."""
import src.api.routes.extracao as extracao_mod
from src.extraction.duplicate_checker import ResultadoDuplicata


class _FakeDB:
    """Sessão fake — scalar sempre retorna None (empresa não encontrada)."""
    def scalar(self, *_a, **_k):
        return None


def _stub_verificar(resultado_dup, msg):
    def _fn(_db, _hash, _empresa_id, _ano):
        return resultado_dup, None, msg
    return _fn


def test_sem_hash_curto_circuita_para_novo():
    resultado = {"empresa": {"cnpj": "12.345.678/0001-90"}}  # sem hash
    extracao_mod._classificar_versionamento(_FakeDB(), resultado)
    assert resultado["status_pcmso"] == "NOVO"


def test_duplicata_exata(monkeypatch):
    monkeypatch.setattr(extracao_mod, "verificar_duplicata",
                        _stub_verificar(ResultadoDuplicata.DUPLICATA_EXATA, "arquivo idêntico"))
    resultado = {"hash": "h" * 64, "empresa": {"cnpj": "12.345.678/0001-90"}}
    extracao_mod._classificar_versionamento(_FakeDB(), resultado)
    assert resultado["status_pcmso"] == "duplicata_exata"
    assert resultado["mensagem_versao"] == "arquivo idêntico"


def test_nova_versao(monkeypatch):
    monkeypatch.setattr(extracao_mod, "verificar_duplicata",
                        _stub_verificar(ResultadoDuplicata.NOVA_VERSAO, "nova versão v2"))
    resultado = {"hash": "h" * 64, "empresa": {"cnpj": "12.345.678/0001-90"}}
    extracao_mod._classificar_versionamento(_FakeDB(), resultado)
    assert resultado["status_pcmso"] == "nova_versao"
    assert "v2" in resultado["mensagem_versao"]


def test_novo_arquivo_sem_mensagem(monkeypatch):
    monkeypatch.setattr(extracao_mod, "verificar_duplicata",
                        _stub_verificar(ResultadoDuplicata.NOVO_ARQUIVO, "arquivo novo"))
    resultado = {"hash": "h" * 64, "empresa": {"cnpj": "12.345.678/0001-90"}}
    extracao_mod._classificar_versionamento(_FakeDB(), resultado)
    assert resultado["status_pcmso"] == "novo_arquivo"
    assert resultado["mensagem_versao"] == ""  # sem ruído para arquivos novos
