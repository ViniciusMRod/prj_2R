"""
Worker de processamento assíncrono de lotes de PDFs (Fase 3).

Lê jobs 'pendente' da tabela lote_jobs, processa cada PDF (extrai + classifica
versão), gera o Excel consolidado e marca 'concluido'. Erro por PDF vai para a
aba Erros (não derruba o lote); erro sistêmico marca 'falhou'.

Uso:
    python scripts/worker_lote.py --once          # processa pendentes e sai (n8n cron)
    python scripts/worker_lote.py --intervalo 5   # loop contínuo (poll a cada 5s)
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

from config.database import SessionLocal  # noqa: E402
from src.database.models import LoteJob, StatusLote  # noqa: E402
from src.api.routes.extracao import _classificar_versionamento  # noqa: E402
from src.extraction.pdf_extractor import extrair_pcmso  # noqa: E402
from src.extraction.excel_builder import gerar_excel  # noqa: E402


def processar_job(db, job) -> None:
    """Processa um job do início ao fim. Idempotente (extração é pura)."""
    try:
        staging = Path(job.staging_dir)
        if not staging.exists():
            job.status = StatusLote.FALHOU
            job.erro_detalhe = f"Diretório de staging não encontrado: {staging}"
            job.finished_at = datetime.now()
            db.commit()
            return

        resultados = []
        for pdf in sorted(staging.glob("*.pdf")):
            try:
                resultado = extrair_pcmso(pdf)
                resultado["arquivo"] = pdf.name
                _classificar_versionamento(db, resultado)
                resultados.append(resultado)
            except Exception as exc:  # isola falha por PDF
                resultados.append({"arquivo": pdf.name, "erros_extracao": [str(exc)]})
                job.com_erro += 1
            job.processados += 1
            db.commit()  # progresso visível ao polling

        excel_path = staging / "resultado.xlsx"
        excel_path.write_bytes(gerar_excel(resultados))
        job.excel_path = str(excel_path)
        job.status = StatusLote.CONCLUIDO
        job.finished_at = datetime.now()
        db.commit()
    except Exception as exc:  # erro sistêmico
        db.rollback()
        job.status = StatusLote.FALHOU
        job.erro_detalhe = str(exc)
        job.finished_at = datetime.now()
        db.commit()


def _resetar_orfaos(db) -> int:
    """Jobs presos em 'processando' (worker morreu) voltam a 'pendente'."""
    orfaos = list(db.scalars(select(LoteJob).where(LoteJob.status == StatusLote.PROCESSANDO)))
    for job in orfaos:
        job.status = StatusLote.PENDENTE
    db.commit()
    return len(orfaos)


def _claim_proximo(db):
    """Pega o job 'pendente' mais antigo de forma atômica (FIFO, SKIP LOCKED)."""
    job = db.scalar(
        select(LoteJob)
        .where(LoteJob.status == StatusLote.PENDENTE)
        .order_by(LoteJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job:
        job.status = StatusLote.PROCESSANDO
        db.commit()
    return job


def executar_worker(once: bool = False, intervalo: float = 5.0) -> None:
    db = SessionLocal()
    try:
        n = _resetar_orfaos(db)
        if n:
            print(f"[worker] {n} job(s) órfão(s) resetado(s) para 'pendente'.")
        while True:
            job = _claim_proximo(db)
            if job:
                print(f"[worker] processando {job.job_uuid} ({job.total_pdfs} PDFs)…")
                processar_job(db, job)
                print(f"[worker] {job.job_uuid} -> {job.status.value} "
                      f"(processados={job.processados}, com_erro={job.com_erro})")
                continue  # busca o próximo imediatamente
            if once:
                break
            time.sleep(intervalo)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de lotes PCMSO (Fase 3).")
    parser.add_argument("--once", action="store_true",
                        help="processa os pendentes e sai (uso com n8n cron)")
    parser.add_argument("--intervalo", type=float, default=5.0,
                        help="segundos entre polls no modo loop (default 5)")
    args = parser.parse_args()
    executar_worker(once=args.once, intervalo=args.intervalo)


if __name__ == "__main__":
    main()
