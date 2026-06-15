"""Testes dos endpoints de lote assíncrono (DB-free via dependency_overrides)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.database import get_db
from src.api.main import app
from src.database.models import StatusLote
import src.api.routes.extracao as extracao_mod


class FakeJob:
    def __init__(self, **kw):
        self.job_uuid = kw.get("job_uuid", "uuid-x")
        self.status = kw.get("status", StatusLote.PENDENTE)
        self.total_pdfs = kw.get("total_pdfs", 0)
        self.processados = kw.get("processados", 0)
        self.com_erro = kw.get("com_erro", 0)
        self.excel_path = kw.get("excel_path")
        self.erro_detalhe = kw.get("erro_detalhe")


class FakeDB:
    def __init__(self, job=None):
        self._job = job
        self.added = []
    def add(self, obj): self.added.append(obj)
    def commit(self): pass
    def scalar(self, *_a, **_k): return self._job


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def test_post_extrair_lote_cria_job_202(tmp_path, monkeypatch):
    monkeypatch.setattr(extracao_mod, "PCMSO_LOTE_STAGING", tmp_path)
    app.dependency_overrides[get_db] = lambda: FakeDB()
    client = TestClient(app)

    resp = client.post("/extrair-lote", files=[
        ("files", ("a.pdf", b"%PDF-a", "application/pdf")),
        ("files", ("b.pdf", b"%PDF-b", "application/pdf")),
    ])

    assert resp.status_code == 202
    body = resp.json()
    assert body["total_pdfs"] == 2
    assert body["status"] == "pendente"
    assert body["job_uuid"]
    # PDFs gravados no staging do job
    staging = tmp_path / body["job_uuid"]
    assert (staging / "a.pdf").read_bytes() == b"%PDF-a"
    assert (staging / "b.pdf").read_bytes() == b"%PDF-b"


def test_post_extrair_lote_sem_arquivo_400():
    app.dependency_overrides[get_db] = lambda: FakeDB()
    client = TestClient(app)
    resp = client.post("/extrair-lote", files=[])
    assert resp.status_code in (400, 422)  # 422 se o FastAPI barrar antes


def test_get_status_lote():
    job = FakeJob(job_uuid="abc", status=StatusLote.PROCESSANDO,
                  total_pdfs=120, processados=47, com_erro=2)
    app.dependency_overrides[get_db] = lambda: FakeDB(job)
    client = TestClient(app)

    resp = client.get("/lote/abc")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "job_uuid": "abc", "status": "processando",
        "total_pdfs": 120, "processados": 47, "com_erro": 2,
        "excel_pronto": False,
    }


def test_get_status_lote_404():
    app.dependency_overrides[get_db] = lambda: FakeDB(None)
    client = TestClient(app)
    assert client.get("/lote/nao-existe").status_code == 404


def test_get_excel_concluido_200(tmp_path):
    xlsx = tmp_path / "resultado.xlsx"
    xlsx.write_bytes(b"PK\x03\x04fake-xlsx")
    job = FakeJob(job_uuid="ok", status=StatusLote.CONCLUIDO, excel_path=str(xlsx))
    app.dependency_overrides[get_db] = lambda: FakeDB(job)
    client = TestClient(app)
    resp = client.get("/lote/ok/excel")
    assert resp.status_code == 200
    assert resp.content == b"PK\x03\x04fake-xlsx"


def test_get_excel_em_processamento_409():
    job = FakeJob(job_uuid="p", status=StatusLote.PROCESSANDO)
    app.dependency_overrides[get_db] = lambda: FakeDB(job)
    client = TestClient(app)
    assert client.get("/lote/p/excel").status_code == 409


def test_get_excel_falhou_422():
    job = FakeJob(job_uuid="f", status=StatusLote.FALHOU, erro_detalhe="staging sumiu")
    app.dependency_overrides[get_db] = lambda: FakeDB(job)
    client = TestClient(app)
    resp = client.get("/lote/f/excel")
    assert resp.status_code == 422
    assert "staging sumiu" in resp.json()["detail"]


def test_get_excel_404():
    app.dependency_overrides[get_db] = lambda: FakeDB(None)
    client = TestClient(app)
    assert client.get("/lote/x/excel").status_code == 404
