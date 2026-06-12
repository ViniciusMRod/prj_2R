"""Round-trip do Excel: hash e status de versionamento devem sobreviver
ao gerar_excel → converter_excel_para_registros (essencial para registrar_versao)."""
from src.extraction.excel_builder import gerar_excel
from src.extraction.excel_converter import converter_excel_para_registros

EXTRACAO = {
    "arquivo": "PCMSO_EmpresaX.pdf",
    "hash": "abc123def456abc123def456abc123def456abc123def456abc123def456aaaa",
    "status_pcmso": "nova_versao",
    "mensagem_versao": "NOVA VERSÃO DETECTADA: já existe PCMSO para empresa_id=1, ano=2026.",
    "empresa": {"razao_social": "EMPRESA X LTDA", "cnpj": "12.345.678/0001-90"},
    "cargos": [{"setor": "ADM", "cargo": "GERENTE", "quantidade": "1"}],
    "riscos": [],
    "exames": [],
    "cargo_exames": [{"cargo": "GERENTE", "setor": "", "risco": "", "tipo_exame": "Audiometria", "periodicidade_meses": 12}],
    "erros_extracao": [],
}


def test_hash_e_status_sobrevivem_ao_roundtrip():
    excel_bytes = gerar_excel([EXTRACAO])
    registros = converter_excel_para_registros(excel_bytes)

    assert len(registros) == 1
    reg = registros[0]
    assert reg["hash"] == EXTRACAO["hash"]
    assert reg["status_pcmso"] == "nova_versao"
    # dados de negócio também preservados
    assert reg["empresa"]["cnpj"] == "12.345.678/0001-90"
    assert reg["cargo_exames"][0]["periodicidade_meses"] == 12


def test_status_default_novo_quando_ausente():
    extracao_sem_status = {**EXTRACAO}
    extracao_sem_status.pop("status_pcmso")
    extracao_sem_status.pop("mensagem_versao")
    registros = converter_excel_para_registros(gerar_excel([extracao_sem_status]))
    assert registros[0]["status_pcmso"] == "NOVO"
    assert registros[0]["hash"] == EXTRACAO["hash"]
