"""Prova e2e do lote assíncrono (Fase 3) contra o banco de teste.

POST /extrair-lote (2 PDFs reais) -> 202 + job_uuid
-> worker --once processa -> GET status = concluido
-> GET excel = 200 (.xlsx válido). Auto-limpa job + staging.

Uso: python scripts/prova_lote_async.py [pdf1 pdf2 ...]
     (default: 2 primeiros PDFs de ../PCMSO)
"""
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from config.database import get_db_context  # noqa: E402
from src.api.main import app  # noqa: E402
from src.database.models import LoteJob  # noqa: E402
import scripts.worker_lote as worker  # noqa: E402


def _pdfs() -> list[Path]:
    args = [Path(a) for a in sys.argv[1:]]
    if args:
        return args
    pasta = Path(__file__).parent.parent.parent / "PCMSO"
    return sorted(pasta.glob("*.pdf"))[:2]


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

    print("\nRESULTADO:", "PASSOU" if ok else "FALHOU")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
