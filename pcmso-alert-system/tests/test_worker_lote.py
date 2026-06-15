"""Testes de processar_job e limpar_staging (DB-free: FakeDB + filesystem real)."""
from datetime import datetime, timedelta

import scripts.worker_lote as worker
from src.database.models import StatusLote


class FakeDB:
    def __init__(self, jobs_para_limpar=None):
        self.commits = 0
        self._jobs = jobs_para_limpar or []

    def commit(self): self.commits += 1
    def rollback(self): pass

    def scalars(self, _stmt):
        return iter(self._jobs)


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


# ---------------------------------------------------------------------------
# limpar_staging
# ---------------------------------------------------------------------------

class FakeLoteJob:
    """Job terminal simulado para testes de limpar_staging."""
    def __init__(self, staging_dir, status=StatusLote.CONCLUIDO, dias_atras=10):
        self.staging_dir = str(staging_dir)
        self.excel_path = str(staging_dir / "resultado.xlsx") if staging_dir else None
        self.status = status
        self.finished_at = datetime.now() - timedelta(days=dias_atras)


def test_limpar_staging_remove_diretorio(tmp_path):
    staging = tmp_path / "job-abc"
    staging.mkdir()
    (staging / "doc.pdf").write_bytes(b"x")

    job = FakeLoteJob(staging, StatusLote.CONCLUIDO, dias_atras=10)
    db = FakeDB(jobs_para_limpar=[job])

    n = worker.limpar_staging(db, ttl_dias=7)

    assert n == 1
    assert not staging.exists()
    assert job.staging_dir is None
    assert job.excel_path is None
    assert db.commits == 1


def test_limpar_staging_staging_ja_ausente_nao_falha(tmp_path):
    """staging_dir já foi removido manualmente — não deve lançar exceção."""
    staging = tmp_path / "job-xyz"  # não criamos o dir

    job = FakeLoteJob(staging, StatusLote.FALHOU, dias_atras=8)
    db = FakeDB(jobs_para_limpar=[job])

    n = worker.limpar_staging(db, ttl_dias=7)

    assert n == 1
    assert job.staging_dir is None
    assert db.commits == 1


def test_limpar_staging_sem_jobs_nao_commita(tmp_path):
    """Nenhum job elegível → nenhum commit."""
    db = FakeDB(jobs_para_limpar=[])
    n = worker.limpar_staging(db, ttl_dias=7)
    assert n == 0
    assert db.commits == 0


def test_limpar_staging_multiplos_jobs(tmp_path):
    dirs = [tmp_path / f"job-{i}" for i in range(3)]
    for d in dirs:
        d.mkdir()

    jobs = [FakeLoteJob(d, StatusLote.CONCLUIDO, dias_atras=10) for d in dirs]
    db = FakeDB(jobs_para_limpar=jobs)

    n = worker.limpar_staging(db, ttl_dias=7)

    assert n == 3
    assert all(not d.exists() for d in dirs)
    assert db.commits == 1
