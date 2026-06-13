"""Prova do fix do upsert de CNPJ na aprovação (Fase 2, item 2).

Cenário do bug: reaprovar a MESMA empresa (nova versão do PCMSO) com o CNPJ
enviado ora sem máscara, ora com máscara. Antes do fix a busca não achava a
empresa existente e o INSERT estourava empresas_cnpj_key.

Aprova 2 validações da mesma empresa (hashes diferentes p/ não bater no unique
de hash) e verifica que existe UMA só Empresa. Auto-limpa o que cria.

Uso: python scripts/prova_upsert_cnpj.py
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

CNPJ_CANONICO = "11.222.333/0001-81"  # CNPJ válido sentinela p/ o teste
CNPJ_SEM_MASCARA = "11222333000181"
RAZAO = "EMPRESA PROVA UPSERT LTDA"


def _dados(hash_arq: str) -> dict:
    return {
        "empresa": {"cnpj": CNPJ_CANONICO, "razao_social": RAZAO},
        "hash": hash_arq,
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
        ValidacaoPendente.pcmso_filename.like("prova_upsert_%"))):
        db.delete(vp)
    db.flush()
    if emp:
        db.delete(emp)
    db.commit()


def _criar_validacao(db, filename: str, hash_arq: str) -> int:
    v = ValidacaoPendente(
        pcmso_filename=filename,
        dados_extraidos=_dados(hash_arq),
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

        v1 = _criar_validacao(db, "prova_upsert_1.pdf", "a" * 64)
        v2 = _criar_validacao(db, "prova_upsert_2.pdf", "b" * 64)

    # 1ª aprovação: CNPJ SEM máscara (gatilho original do bug)
    r1 = client.post(f"/validacao/{v1}/aprovar", data={
        "acao": "aprovar", "cnpj": CNPJ_SEM_MASCARA, "razao_social": RAZAO,
        "ano_referencia": "2026", "validado_por": "prova",
    }, follow_redirects=False)

    # 2ª aprovação (reaprovação): MESMA empresa, CNPJ COM máscara
    r2 = client.post(f"/validacao/{v2}/aprovar", data={
        "acao": "aprovar", "cnpj": CNPJ_CANONICO, "razao_social": RAZAO,
        "ano_referencia": "2026", "validado_por": "prova",
    }, follow_redirects=False)

    print(f"aprovacao 1 (sem mascara) -> HTTP {r1.status_code} (esperado 303)")
    print(f"aprovacao 2 (com mascara) -> HTTP {r2.status_code} (esperado 303)")

    ok = True
    with get_db_context() as db:
        n = db.scalar(select(func.count()).select_from(Empresa).where(
            Empresa.cnpj == CNPJ_CANONICO))
        emp = db.scalar(select(Empresa).where(Empresa.cnpj == CNPJ_CANONICO))
        nver = db.scalar(select(func.count()).select_from(PcmsoVersao).where(
            PcmsoVersao.empresa_id == emp.id)) if emp else 0
        print(f"empresas com o CNPJ      -> {n} (esperado 1)")
        print(f"cnpj gravado             -> {emp.cnpj if emp else None} (esperado {CNPJ_CANONICO})")
        print(f"versoes registradas      -> {nver} (esperado 2)")
        ok = (r1.status_code == 303 and r2.status_code == 303
              and n == 1 and emp and emp.cnpj == CNPJ_CANONICO and nver == 2)
        _limpar(db)  # auto-limpeza: banco volta ao estado anterior

    print("\nRESULTADO:", "PASSOU ✔" if ok else "FALHOU �’")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
