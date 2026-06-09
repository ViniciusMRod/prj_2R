"""
Calibração do score de confiança: roda extrair_pcmso em todos os PDFs
de uma pasta e imprime a tabela de scores para ajuste de pesos/cortes.

Uso:
    python scripts/calibrar_confianca.py [pasta_pdfs]   # default: ../PCMSO
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.pdf_extractor import extrair_pcmso  # noqa: E402


def main() -> None:
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent / "PCMSO"
    pdfs = sorted(pasta.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF em {pasta}")
        sys.exit(1)

    linhas = []
    for pdf in pdfs:
        try:
            r = extrair_pcmso(pdf)
            c = r.get("confianca", {})
            linhas.append({
                "arquivo": pdf.name[:45],
                "nivel": c.get("nivel", "?"),
                "geral": c.get("score_geral", 0),
                "empresa": c.get("score_empresa", 0),
                "estrutura": c.get("score_estrutura", 0),
                "volume": c.get("score_volume", 0),
                "cargos": len(r.get("cargos", [])),
                "exames": len(r.get("cargo_exames", [])),
                "avisos": c.get("avisos", []),
            })
        except Exception as e:  # noqa: BLE001
            linhas.append({"arquivo": pdf.name[:45], "nivel": "ERRO", "geral": 0,
                           "empresa": 0, "estrutura": 0, "volume": 0,
                           "cargos": 0, "exames": 0, "avisos": [str(e)]})

    print(f"\n{'ARQUIVO':<47}{'NIVEL':<7}{'GERAL':<7}{'EMP':<6}{'ESTR':<6}{'VOL':<6}{'CRG':<5}{'EXM':<5}")
    print("-" * 89)
    for l in linhas:
        print(f"{l['arquivo']:<47}{l['nivel']:<7}{l['geral']:<7.3f}"
              f"{l['empresa']:<6.2f}{l['estrutura']:<6.2f}{l['volume']:<6.2f}"
              f"{l['cargos']:<5}{l['exames']:<5}")

    print("\nAVISOS POR ARQUIVO:")
    for l in linhas:
        if l["avisos"]:
            print(f"\n  {l['arquivo']}")
            for a in l["avisos"]:
                print(f"    - {a}")

    niveis = [l["nivel"] for l in linhas]
    print(f"\nRESUMO: {len(linhas)} PDFs | ALTA={niveis.count('ALTA')} "
          f"MEDIA={niveis.count('MEDIA')} BAIXA={niveis.count('BAIXA')} ERRO={niveis.count('ERRO')}")


if __name__ == "__main__":
    main()
