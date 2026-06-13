"""Prova do guard de duplicata exata na aprovação (Fase 2, item 3).

Cenário do bug: aprovar o MESMO PDF (mesmo hash) duas vezes. Antes do guard, a
2ª aprovação estourava IntegrityError no unique de PcmsoVersao.hash_arquivo.

Aprova 2 validações com o MESMO hash e verifica que a 2ª é bloqueada com aviso
amigável (HTTP 303 + ?mensagem_aviso=...) e que só existe UMA versão registrada.
Auto-limpa o que cria.

Uso: python scripts/prova_guard_duplicata.py
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
from src.database.models import (  # noqa: E402
    CargoExame, Colaborador, Empresa, Exame,
    PcmsoVersao, ValidacaoPendente, StatusValidacao,
)

CNPJ_CANONICO = "11.222.333/0001-81"
RAZAO = "EMPRESA PROVA GUARD LTDA"
HASH = "c" * 64  # mesmo hash nas duas aprovações = duplicata exata


def _dados() -> dict:
    return {
        "empresa": {"cnpj": CNPJ_CANONICO, "razao_social": RAZAO},
        "hash": HASH,
        "cargo_exames": [
            {"cargo": "AUXILIAR", "tipo_exame": "Hemograma Completo",
             "periodicidade_meses": 12},
        ],
        "exames": [],
        "colaboradores": [],
    }


def _limpar(db) -> None:
    emp = db.scalar(select(Empresa).where(Empresa.cnpj == CNPJ_CANONICO))
    if emp:
        for col in db.scalars(select(Colaborador).where(Colaborador.empresa_id == emp.id)):
            for ex in db.scalars(select(Exame).where(Exame.colaborador_id == col.id)):
                db.delete(ex)
            db.delete(col)
        for ce in db.scalars(select(CargoExame).where(CargoExame.empresa_id == emp.id)):
            db.delete(ce)
        for v in db.scalars(select(PcmsoVersao).where(PcmsoVersao.empresa_id == emp.id)):
            db.delete(v)
        db.flush()
    for vp in db.scalars(select(ValidacaoPendente).where(
        ValidacaoPendente.pcmso_filename.like("prova_guard_%"))):
        db.delete(vp)
    db.flush()
    if emp:
        db.delete(emp)
    db.commit()


def _criar_validacao(db, filename: str) -> int:
    v = ValidacaoPendente(
        pcmso_filename=filename,
        dados_extraidos=_dados(),
        status=StatusValidacao.PENDENTE,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v.id


def main() -> None:
    from fastapi.testclient import TestClient
    from src.validation_interface.web_validator import app

    client = TestClient(app)

    with get_db_context() as db:
        _limpar(db)
        v1 = _criar_validacao(db, "prova_guard_1.pdf")
        v2 = _criar_validacao(db, "prova_guard_2.pdf")

    form = {"acao": "aprovar", "cnpj": CNPJ_CANONICO, "razao_social": RAZAO,
            "ano_referencia": "2026", "validado_por": "prova"}

    r1 = client.post(f"/validacao/{v1}/aprovar", data=form, follow_redirects=False)
    r2 = client.post(f"/validacao/{v2}/aprovar", data=form, follow_redirects=False)

    loc1 = r1.headers.get("location", "")
    loc2 = r2.headers.get("location", "")
    print(f"aprovacao 1 -> HTTP {r1.status_code}  location={loc1[:60]}")
    print(f"aprovacao 2 -> HTTP {r2.status_code}  location={loc2[:60]}")

    with get_db_context() as db:
        emp = db.scalar(select(Empresa).where(Empresa.cnpj == CNPJ_CANONICO))
        nver = db.scalar(select(func.count()).select_from(PcmsoVersao).where(
            PcmsoVersao.empresa_id == emp.id)) if emp else 0
        print(f"versoes registradas -> {nver} (esperado 1)")
        ok = (
            r1.status_code == 303 and "mensagem_sucesso" in loc1
            and r2.status_code == 303 and "mensagem_aviso" in loc2
            and nver == 1
        )
        _limpar(db)

    print("\nRESULTADO:", "PASSOU" if ok else "FALHOU")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
