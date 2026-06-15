"""Prova e2e do lote assíncrono (Fase 3) contra o banco de teste.

POST /extrair-lote (2 PDFs reais) -> 202 + job_uuid
-> worker --once processa -> GET status = concluido
-> GET excel = 200 (.xlsx válido). Auto-limpa job + staging.

Cenário 2: insere job com status=PROCESSANDO diretamente no banco
(simula worker morto no meio do job) -> worker --once faz
_resetar_orfaos (PROCESSANDO->pendente) + _claim_proximo -> concluido.

Uso: python scripts/prova_lote_async.py [pdf1 pdf2 ...]
     (default: 2 primeiros PDFs de ../PCMSO)
"""
import shutil
import sys
from pathlib import Path
from uuid import uuid4

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from config.database import get_db_context  # noqa: E402
from src.api.main import app  # noqa: E402
from src.api.routes.extracao import PCMSO_LOTE_STAGING  # noqa: E402
from src.database.models import LoteJob, StatusLote  # noqa: E402
import scripts.worker_lote as worker  # noqa: E402


def _pdfs() -> list[Path]:
    args = [Path(a) for a in sys.argv[1:]]
    if args:
        return args
    pasta = Path(__file__).parent.parent.parent / "PCMSO"
    return sorted(pasta.glob("*.pdf"))[:2]


def _provar_reset_orfao(pdf_origem: Path) -> bool:
    """Prova que o worker reseta jobs PROCESSANDO (orfaos) e os processa."""
    job_uuid = "prova-orfao-" + uuid4().hex[:8]
    staging = PCMSO_LOTE_STAGING / job_uuid
    staging.mkdir(parents=True, exist_ok=True)
    (staging / pdf_origem.name).write_bytes(pdf_origem.read_bytes())

    with get_db_context() as db:
        job = LoteJob(
            job_uuid=job_uuid,
            status=StatusLote.PROCESSANDO,
            total_pdfs=1,
            processados=0,
            com_erro=0,
            staging_dir=str(staging),
        )
        db.add(job)
        db.commit()

    # worker deve: resetar orfao (PROCESSANDO->pendente), claim, processar
    worker.executar_worker(once=True)

    with get_db_context() as db:
        job = db.scalar(select(LoteJob).where(LoteJob.job_uuid == job_uuid))
        status_final = job.status if job else None
        resultado = status_final == StatusLote.CONCLUIDO
        print(f"reset de orfao -> job PROCESSANDO virou {status_final} (esperado concluido)")
        # limpeza
        shutil.rmtree(staging, ignore_errors=True)
        if job:
            db.delete(job)
        db.commit()

    return resultado


def main() -> None:
    pdfs = _pdfs()
    if not pdfs:
        print("Nenhum PDF encontrado."); sys.exit(1)

    client = TestClient(app)
    arquivos = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs]
    resp = client.post("/extrair-lote", files=arquivos)
    print(f"POST /extrair-lote -> HTTP {resp.status_code} (esperado 202)")
    job_uuid = resp.json().get("job_uuid")
    total = resp.json().get("total_pdfs")
    print(f"  job_uuid={job_uuid} total_pdfs={total}")

    # worker processa de forma síncrona (--once)
    worker.executar_worker(once=True)

    st = client.get(f"/lote/{job_uuid}").json()
    print(f"GET status -> {st['status']} (esperado concluido) "
          f"processados={st['processados']}/{st['total_pdfs']} com_erro={st['com_erro']}")

    exc = client.get(f"/lote/{job_uuid}/excel")
    print(f"GET excel -> HTTP {exc.status_code} (esperado 200) bytes={len(exc.content)}")

    ok = (resp.status_code == 202 and st["status"] == "concluido"
          and st["processados"] == total and exc.status_code == 200
          and exc.content[:2] == b"PK")

    # auto-limpeza: remove staging e o registro do job
    with get_db_context() as db:
        job = db.scalar(select(LoteJob).where(LoteJob.job_uuid == job_uuid))
        if job:
            shutil.rmtree(job.staging_dir, ignore_errors=True)
            db.delete(job)
        db.commit()

    ok_orfao = _provar_reset_orfao(pdfs[0])
    ok = ok and ok_orfao

    print("\nRESULTADO:", "PASSOU" if ok else "FALHOU")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
