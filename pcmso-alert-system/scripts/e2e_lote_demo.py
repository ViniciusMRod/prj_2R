"""
Demo ponta-a-ponta do fluxo de lote + versionamento (fase de testes).

Para cada PDF de exemplo:
  extrair_pcmso -> gerar_excel -> converter (round-trip do analista)
  -> cria ValidacaoPendente -> aprova via endpoint REAL (TestClient)
  -> registra versão no PostgreSQL.

Depois, prova a detecção de duplicata/versão com verificar_duplicata.
Mostra pcmso_versoes ANTES e DEPOIS. Escreve no banco de TESTE (descartável).

Uso:
    python scripts/e2e_lote_demo.py [pdf1 pdf2 ...]   # default: 2 primeiros de ../PCMSO
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select  # noqa: E402

from config.database import get_db_context  # noqa: E402
from src.database.models import PcmsoVersao, ValidacaoPendente, StatusValidacao  # noqa: E402
from src.extraction.pdf_extractor import extrair_pcmso  # noqa: E402
from src.extraction.excel_builder import gerar_excel  # noqa: E402
from src.extraction.excel_converter import converter_excel_para_registros  # noqa: E402
from src.extraction.duplicate_checker import ResultadoDuplicata, verificar_duplicata  # noqa: E402


def _contar_versoes(db) -> int:
    return db.scalar(select(func.count()).select_from(PcmsoVersao))


def _registro_apos_roundtrip(pdf: Path) -> dict:
    """Extrai e passa pelo Excel ida-e-volta, como faria o analista."""
    resultado = extrair_pcmso(pdf)
    resultado["arquivo"] = pdf.name
    excel = gerar_excel([resultado])
    registros = converter_excel_para_registros(excel)
    reg = registros[0]
    # garante campos usados pela aprovação
    reg.setdefault("empresa", resultado.get("empresa", {}))
    reg["arquivo"] = pdf.name
    return reg


def _aprovar(client, db, reg: dict) -> None:
    emp = reg.get("empresa", {}) or {}
    cnpj = emp.get("cnpj", "") or "00.000.000/0000-00"
    razao = emp.get("razao_social", "") or "EMPRESA EXEMPLO"
    ano = emp.get("ano_referencia") or 2026

    v = ValidacaoPendente(
        pcmso_filename=reg["arquivo"],
        dados_extraidos=reg,
        status=StatusValidacao.PENDENTE,
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    resp = client.post(
        f"/validacao/{v.id}/aprovar",
        data={
            "acao": "aprovar",
            "cnpj": cnpj,
            "razao_social": razao,
            "ano_referencia": str(ano),
            "validado_por": "demo-e2e",
        },
        follow_redirects=False,
    )
    print(f"  aprovar '{reg['arquivo'][:40]}…' -> HTTP {resp.status_code} "
          f"(hash={(reg.get('hash') or '')[:12]}… cnpj={cnpj} ano={ano})")


def main() -> None:
    from fastapi.testclient import TestClient
    from src.validation_interface.web_validator import app

    args = [Path(a) for a in sys.argv[1:]]
    if args:
        pdfs = args
    else:
        pasta = Path(__file__).parent.parent.parent / "PCMSO"
        pdfs = sorted(pasta.glob("*.pdf"))[:2]

    if not pdfs:
        print("Nenhum PDF encontrado.")
        sys.exit(1)

    client = TestClient(app)

    with get_db_context() as db:
        antes = _contar_versoes(db)
        print(f"\npcmso_versoes ANTES: {antes}")

        print("\n--- APROVANDO LOTE ---")
        registros = []
        for pdf in pdfs:
            reg = _registro_apos_roundtrip(pdf)
            registros.append(reg)
            _aprovar(client, db, reg)

        db.expire_all()
        depois = _contar_versoes(db)
        print(f"\npcmso_versoes DEPOIS: {depois}  (delta +{depois - antes})")

        # Prova de detecção usando o primeiro registro aprovado
        primeiro = registros[0]
        h = primeiro.get("hash", "")
        emp = primeiro.get("empresa", {}) or {}
        from src.database.models import Empresa
        empresa = db.scalar(select(Empresa).where(Empresa.cnpj == emp.get("cnpj", "")))
        emp_id = empresa.id if empresa else 0
        ano = emp.get("ano_referencia") or 2026

        print("\n--- PROVA DE DETECÇÃO (verificar_duplicata) ---")
        r1, _, _ = verificar_duplicata(db, h, emp_id, ano)
        print(f"  mesmo hash            -> {r1.value}  (esperado: duplicata_exata)")

        r2, _, _ = verificar_duplicata(db, "f" * 64, emp_id, ano)
        print(f"  hash novo, msm ano    -> {r2.value}  (esperado: nova_versao)")

        r3, _, _ = verificar_duplicata(db, "e" * 64, 999999, 1900)
        print(f"  empresa/ano inéditos  -> {r3.value}  (esperado: novo_arquivo)")

    print()


if __name__ == "__main__":
    main()
