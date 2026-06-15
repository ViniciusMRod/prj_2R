"""
Worker de processamento assíncrono de lotes de PDFs (Fase 3).

Lê jobs 'pendente' da tabela lote_jobs, processa cada PDF (extrai + classifica
versão), gera o Excel consolidado e marca 'concluido'. Erro por PDF vai para a
aba Erros (não derruba o lote); erro sistêmico marca 'falhou'.

Uso:
    python scripts/worker_lote.py --once          # processa pendentes e sai (n8n cron)
    python scripts/worker_lote.py --intervalo 5   # loop contínuo (poll a cada 5s)
"""
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import StatusLote  # noqa: E402
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
