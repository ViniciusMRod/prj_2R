"""
Gera os golden files da extração (Fase 2 — congelar comportamento).

Para cada PDF da pasta ../PCMSO, roda extrair_pcmso e grava o resultado
completo em tests/golden/<nome>.json. Os JSONs são deliberadamente NÃO
versionados (*.json no .gitignore — LGPD): existem só na máquina local,
como rede de regressão enquanto mexemos na normalização do catálogo.

Uso:
    python scripts/gerar_golden_files.py [--sobrescrever]
"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.pdf_extractor import extrair_pcmso  # noqa: E402

PASTA_PCMSO = Path(__file__).resolve().parents[2] / "PCMSO"
PASTA_GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden"


def main() -> None:
    sobrescrever = "--sobrescrever" in sys.argv

    pdfs = sorted(PASTA_PCMSO.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF em {PASTA_PCMSO}")
        sys.exit(1)

    PASTA_GOLDEN.mkdir(parents=True, exist_ok=True)

    gerados, pulados = 0, 0
    for pdf in pdfs:
        destino = PASTA_GOLDEN / f"{pdf.stem}.json"
        if destino.exists() and not sobrescrever:
            print(f"  pulado (já existe): {destino.name[:60]}")
            pulados += 1
            continue

        resultado = extrair_pcmso(pdf)
        destino.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(
            f"  gerado: {pdf.name[:55]:<55} "
            f"cargo_exames={len(resultado['cargo_exames']):>3} "
            f"confianca={resultado['confianca']['nivel']}"
        )
        gerados += 1

    print(f"\n{gerados} golden file(s) gerado(s), {pulados} pulado(s) em {PASTA_GOLDEN}")
    if pulados and not sobrescrever:
        print("Use --sobrescrever para regenerar os existentes (só após mudança INTENCIONAL).")


if __name__ == "__main__":
    main()
