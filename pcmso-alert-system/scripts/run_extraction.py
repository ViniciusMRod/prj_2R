"""
Script de extração manual de um PCMSO PDF.
Útil para testar a extração sem passar pelo n8n.

Uso:
    python scripts/run_extraction.py data/pcmso_raw/PCMSO_empresa.pdf
    python scripts/run_extraction.py data/pcmso_raw/PCMSO_empresa.pdf --inserir
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai dados de um PCMSO PDF")
    parser.add_argument("filepath", help="Caminho para o PDF do PCMSO")
    parser.add_argument("--inserir", action="store_true",
                        help="Inserir direto na fila de validação (sem confirmar)")
    args = parser.parse_args()

    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"❌ Arquivo não encontrado: {filepath}")
        sys.exit(1)

    print(f"=== Extração: {filepath.name} ===\n")

    from src.extraction.pdf_extractor import extrair_pcmso, salvar_json_extracao
    from src.extraction.validators import validar_dados_extraidos

    dados = extrair_pcmso(filepath)

    print(f"Hash: {dados['hash'][:16]}...")
    empresa = dados['empresa']
    print(f"Empresa: {empresa.get('razao_social', '')} | CNPJ: {empresa.get('cnpj', '')}")
    print(f"Cargos: {len(dados['cargos'])}")
    print(f"Riscos: {len(dados['riscos'])}")
    print(f"Exames (PCMSO): {len(dados['exames'])}")
    print(f"Mapeamentos cargo-exame: {len(dados['cargo_exames'])}")

    resultado = validar_dados_extraidos(dados)
    print(f"\nValidação: {'✅ OK' if resultado['valido'] else '❌ Com erros'}")
    for e in resultado["erros"]:
        print(f"  ❌ {e}")
    for a in resultado["avisos"]:
        print(f"  ⚠️  {a}")
    # Salvar JSON
    json_path = filepath.parent / f"{filepath.stem}_extraido.json"
    salvar_json_extracao(dados, json_path)
    print(f"\n✓ JSON salvo em: {json_path}")

    if args.inserir:
        from config.database import get_db_context
        from src.database.models import ValidacaoPendente
        with get_db_context() as db:
            v = ValidacaoPendente(
                pcmso_filename=filepath.name,
                dados_extraidos=dados,
            )
            db.add(v)
        print(f"✓ Inserido na fila de validação (id={v.id})")
        print(f"  Acesse: http://localhost:5000/validacao/{v.id}")


if __name__ == "__main__":
    main()
