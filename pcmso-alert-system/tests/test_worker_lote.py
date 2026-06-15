"""Testes de processar_job (DB-free: FakeDB + filesystem real)."""
import scripts.worker_lote as worker
from src.database.models import StatusLote


class FakeDB:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class FakeJob:
    def __init__(self, staging_dir, total):
        self.staging_dir = staging_dir
        self.status = StatusLote.PROCESSANDO
        self.total_pdfs = total
        self.processados = 0
        self.com_erro = 0
        self.excel_path = None
        self.erro_detalhe = None
        self.finished_at = None


def _mk_pdfs(tmp_path, nomes):
    for n in nomes:
        (tmp_path / n).write_bytes(b"%PDF-fake")


def test_processar_job_sucesso(tmp_path, monkeypatch):
    _mk_pdfs(tmp_path, ["a.pdf", "b.pdf"])
    monkeypatch.setattr(worker, "extrair_pcmso",
                        lambda p: {"empresa": {"razao_social": "X", "cnpj": "1"}})
    monkeypatch.setattr(worker, "_classificar_versionamento", lambda db, r: None)

    job = FakeJob(str(tmp_path), 2)
    worker.processar_job(FakeDB(), job)

    assert job.status == StatusLote.CONCLUIDO
    assert job.processados == 2
    assert job.com_erro == 0
    assert job.excel_path and (tmp_path / "resultado.xlsx").exists()
    assert job.finished_at is not None


def test_processar_job_pdf_quebrado_isola_erro(tmp_path, monkeypatch):
    _mk_pdfs(tmp_path, ["ok.pdf", "ruim.pdf"])

    def _extrai(p):
        if p.name == "ruim.pdf":
            raise ValueError("pdf corrompido")
        return {"empresa": {"razao_social": "X", "cnpj": "1"}}

    monkeypatch.setattr(worker, "extrair_pcmso", _extrai)
    monkeypatch.setattr(worker, "_classificar_versionamento", lambda db, r: None)

    job = FakeJob(str(tmp_path), 2)
    worker.processar_job(FakeDB(), job)

    assert job.status == StatusLote.CONCLUIDO
    assert job.processados == 2
    assert job.com_erro == 1


def test_processar_job_staging_ausente_falha(tmp_path):
    job = FakeJob(str(tmp_path / "nao-existe"), 0)
    worker.processar_job(FakeDB(), job)
    assert job.status == StatusLote.FALHOU
    assert job.erro_detalhe
