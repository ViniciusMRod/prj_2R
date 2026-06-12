"""
Golden-file tests da extração (Fase 2 — congelar comportamento).

Compara o resultado atual de extrair_pcmso com o snapshot salvo em
tests/golden/<nome>.json. Qualquer mudança no extrator que altere o
output dos 14 PDFs de exemplo aparece aqui como divergência detalhada.

Goldens são locais (LGPD) — gere com: python scripts/gerar_golden_files.py
Sem PDFs ou sem goldens, os testes são pulados.
"""
import json
from pathlib import Path

import pytest

PASTA_PCMSO = Path(__file__).resolve().parents[2] / "PCMSO"
PASTA_GOLDEN = Path(__file__).resolve().parent / "golden"

PDFS = sorted(PASTA_PCMSO.glob("*.pdf")) if PASTA_PCMSO.is_dir() else []

MAX_DIVERGENCIAS = 10


def _diff(caminho: str, esperado, atual, erros: list[str]) -> None:
    """Compara recursivamente e acumula divergências legíveis (até o limite)."""
    if len(erros) >= MAX_DIVERGENCIAS:
        return
    if type(esperado) is not type(atual):
        erros.append(
            f"{caminho}: tipo {type(esperado).__name__} -> {type(atual).__name__}"
        )
    elif isinstance(esperado, dict):
        for chave in sorted(set(esperado) | set(atual)):
            if chave not in atual:
                erros.append(f"{caminho}.{chave}: chave sumiu")
            elif chave not in esperado:
                erros.append(f"{caminho}.{chave}: chave nova (valor={atual[chave]!r})")
            else:
                _diff(f"{caminho}.{chave}", esperado[chave], atual[chave], erros)
    elif isinstance(esperado, list):
        if len(esperado) != len(atual):
            erros.append(f"{caminho}: {len(esperado)} itens -> {len(atual)} itens")
        for i, (e, a) in enumerate(zip(esperado, atual)):
            _diff(f"{caminho}[{i}]", e, a, erros)
    elif esperado != atual:
        erros.append(f"{caminho}: {esperado!r} -> {atual!r}")


@pytest.mark.parametrize("pdf", PDFS, ids=lambda p: p.stem[:50])
def test_extracao_bate_com_golden(pdf: Path):
    golden_path = PASTA_GOLDEN / f"{pdf.stem}.json"
    if not golden_path.exists():
        pytest.skip("golden ausente — rode: python scripts/gerar_golden_files.py")

    from src.extraction.pdf_extractor import extrair_pcmso

    esperado = json.loads(golden_path.read_text(encoding="utf-8"))
    # round-trip por JSON normaliza tipos (tuplas->listas) como no golden
    atual = json.loads(json.dumps(extrair_pcmso(pdf), ensure_ascii=False))

    erros: list[str] = []
    _diff("resultado", esperado, atual, erros)
    assert not erros, (
        f"Extração divergiu do golden ({len(erros)}+ divergência(s)):\n  "
        + "\n  ".join(erros)
        + "\nSe a mudança foi intencional: python scripts/gerar_golden_files.py --sobrescrever"
    )


def test_ha_pdfs_de_exemplo():
    if not PDFS:
        pytest.skip(f"pasta {PASTA_PCMSO} sem PDFs (CI/clone limpo)")
    assert len(PDFS) >= 1
