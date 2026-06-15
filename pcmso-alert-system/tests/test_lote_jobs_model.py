"""Testes puros do model LoteJob / enum StatusLote (sem banco)."""
from src.database.models import LoteJob, StatusLote


def test_status_lote_tem_quatro_estados():
    valores = {s.value for s in StatusLote}
    assert valores == {"pendente", "processando", "concluido", "falhou"}


def test_lote_job_tablename_e_colunas():
    assert LoteJob.__tablename__ == "lote_jobs"
    cols = LoteJob.__table__.columns
    for nome in ("job_uuid", "status", "total_pdfs", "processados",
                 "com_erro", "staging_dir", "excel_path", "erro_detalhe",
                 "finished_at", "created_at", "updated_at"):
        assert nome in cols
    assert cols["job_uuid"].unique is True
