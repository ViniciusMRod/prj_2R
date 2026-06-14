# Fase 3 — Ingestão assíncrona de lotes grandes de PDFs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar `POST /extrair-lote` assíncrono (aceita o lote e devolve `job_uuid`), processado em segundo plano por um worker PDF a PDF, com status consultável e Excel para download — suportando 50–300 PDFs sem timeout.

**Architecture:** Fila de jobs numa tabela PostgreSQL nova (`lote_jobs`), sem dependência externa. O endpoint grava os PDFs em staging e cria um job `pendente`. Um worker (`scripts/worker_lote.py`) faz claim atômico (`FOR UPDATE SKIP LOCKED`), processa cada PDF (reusando o extrator e o `gerar_excel` atuais), commita progresso por PDF e finaliza em `concluido`/`falhou`. Recuperação de órfão por reset no start.

**Tech Stack:** Python, FastAPI, SQLAlchemy 2.0 (Mapped), PostgreSQL (JSONB + SKIP LOCKED), openpyxl, pytest + FastAPI TestClient.

**Spec:** `docs/superpowers/specs/2026-06-14-fase3-lote-assincrono-design.md`

**Convenção de testes (Fases 1–2):** a suíte `pytest` é **DB-free** — lógica pura com fakes e `app.dependency_overrides`. O que exige PostgreSQL real fica em **provas e2e auto-limpantes** dentro de `scripts/` (fora do `pytest`), como `prova_upsert_cnpj.py`/`prova_guard_duplicata.py`.

---

## File Structure

- **Modify** `src/database/models.py` — adicionar enum `StatusLote` + model `LoteJob` (10ª tabela).
- **Modify** `src/api/routes/extracao.py` — `POST /extrair-lote` assíncrono (202) + `GET /lote/{job_uuid}` + `GET /lote/{job_uuid}/excel` + env `PCMSO_LOTE_STAGING`.
- **Create** `scripts/worker_lote.py` — `processar_job(db, job)` + `_resetar_orfaos(db)` + `_claim_proximo(db)` + `executar_worker(once, intervalo)` + CLI.
- **Create** `tests/test_lote_jobs_model.py` — testes puros do model/enum.
- **Create** `tests/test_lote_endpoints.py` — testes dos 3 endpoints via TestClient + `dependency_overrides` (DB-free).
- **Create** `tests/test_worker_lote.py` — testes de `processar_job` com FakeDB + filesystem (DB-free).
- **Create** `scripts/prova_lote_async.py` — prova e2e auto-limpante (DB real).
- **Modify** `n8n_workflows/workflow_upload_pcmso.json` — POST→download com retry (polling).
- **Modify** `pcmso-alert-system/docs/manual_admin.md` — seções 8, 9 e 11.

---

## Task 1: Model `LoteJob` + enum `StatusLote`

**Files:**
- Modify: `src/database/models.py`
- Test: `tests/test_lote_jobs_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lote_jobs_model.py
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
                 "finished_at"):
        assert nome in cols
    assert cols["job_uuid"].unique is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lote_jobs_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'LoteJob'`.

- [ ] **Step 3: Add enum and model**

Em `src/database/models.py`, após o enum `StatusDemanda` (bloco de Enums), adicionar:

```python
class StatusLote(str, enum.Enum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"
```

E no fim do arquivo (após a tabela `Demanda`), adicionar a 10ª tabela:

```python
# ---------------------------------------------------------------------------
# Tabela 10: Jobs de lote (ingestão assíncrona de PDFs)
# ---------------------------------------------------------------------------

class LoteJob(Base):
    """Job de processamento assíncrono de um lote de PDFs de PCMSO."""
    __tablename__ = "lote_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_uuid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    status: Mapped[StatusLote] = mapped_column(
        Enum(StatusLote), default=StatusLote.PENDENTE, nullable=False
    )
    total_pdfs: Mapped[int] = mapped_column(Integer, nullable=False)
    processados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    com_erro: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    staging_dir: Mapped[str] = mapped_column(String(500), nullable=False)
    excel_path: Mapped[Optional[str]] = mapped_column(String(500))
    erro_detalhe: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<LoteJob {self.job_uuid} {self.status} {self.processados}/{self.total_pdfs}>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lote_jobs_model.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Criar a tabela no banco**

Run: `python scripts/init_database.py`
Expected: lista de tabelas inclui `lote_jobs` (usa `create_all`, não dropa as existentes).

- [ ] **Step 6: Commit**

```bash
git add src/database/models.py tests/test_lote_jobs_model.py
git commit -m "feat(fase3): tabela lote_jobs + enum StatusLote"
```

---

## Task 2: `POST /extrair-lote` assíncrono (202 + job)

**Files:**
- Modify: `src/api/routes/extracao.py`
- Test: `tests/test_lote_endpoints.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lote_endpoints.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lote_endpoints.py::test_post_extrair_lote_cria_job_202 -v`
Expected: FAIL — resposta atual é 200 com Excel (contrato antigo).

- [ ] **Step 3: Reescrever o endpoint POST**

Em `src/api/routes/extracao.py`, ajustar imports do topo:

```python
import os
import uuid
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from src.database.models import Empresa, LoteJob, StatusLote
from src.extraction.duplicate_checker import ResultadoDuplicata, verificar_duplicata
from src.extraction.pdf_extractor import extrair_pcmso
from src.extraction.excel_builder import gerar_excel

router = APIRouter(tags=["Extração"])

PCMSO_LOTE_STAGING = Path(os.getenv("PCMSO_LOTE_STAGING", "data/pcmso_lote_staging/"))
```

Manter `_classificar_versionamento` e `_processar_pdf` como estão (o worker reusa `_classificar_versionamento`; `_processar_pdf` pode permanecer para compatibilidade, mas não é mais usado pelo endpoint).

Substituir a função `extrair_lote` inteira por:

```python
@router.post("/extrair-lote", status_code=202,
             summary="Aceita N PDFs e cria um job de extração assíncrono")
async def extrair_lote(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Recebe N PDFs, grava em staging e cria um job 'pendente'.
    Devolve o job_uuid imediatamente (HTTP 202). O worker processa em background.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    job_uuid = str(uuid.uuid4())
    staging = PCMSO_LOTE_STAGING / job_uuid
    staging.mkdir(parents=True, exist_ok=True)

    total = 0
    for f in files:
        nome = f.filename or f"arquivo_{total}.pdf"
        with open(staging / nome, "wb") as out:
            shutil.copyfileobj(f.file, out)
        total += 1

    job = LoteJob(
        job_uuid=job_uuid,
        status=StatusLote.PENDENTE,
        total_pdfs=total,
        staging_dir=str(staging),
    )
    db.add(job)
    db.commit()

    return {"job_uuid": job_uuid, "total_pdfs": total, "status": StatusLote.PENDENTE.value}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_lote_endpoints.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/extracao.py tests/test_lote_endpoints.py
git commit -m "feat(fase3): POST /extrair-lote assincrono (202 + job)"
```

---

## Task 3: `GET /lote/{job_uuid}` (status/progresso)

**Files:**
- Modify: `src/api/routes/extracao.py`
- Test: `tests/test_lote_endpoints.py`

- [ ] **Step 1: Write the failing test** (acrescentar ao arquivo)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lote_endpoints.py::test_get_status_lote -v`
Expected: FAIL — 404 (rota inexistente).

- [ ] **Step 3: Adicionar o endpoint** (em `src/api/routes/extracao.py`, após o POST)

```python
@router.get("/lote/{job_uuid}", summary="Status e progresso de um job de lote")
def status_lote(job_uuid: str, db: Session = Depends(get_db)):
    job = db.scalar(select(LoteJob).where(LoteJob.job_uuid == job_uuid))
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return {
        "job_uuid": job.job_uuid,
        "status": job.status.value,
        "total_pdfs": job.total_pdfs,
        "processados": job.processados,
        "com_erro": job.com_erro,
        "excel_pronto": job.status == StatusLote.CONCLUIDO,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_lote_endpoints.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/extracao.py tests/test_lote_endpoints.py
git commit -m "feat(fase3): GET /lote/{uuid} status e progresso"
```

---

## Task 4: `GET /lote/{job_uuid}/excel` (download)

**Files:**
- Modify: `src/api/routes/extracao.py`
- Test: `tests/test_lote_endpoints.py`

- [ ] **Step 1: Write the failing test** (acrescentar ao arquivo)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lote_endpoints.py::test_get_excel_concluido_200 -v`
Expected: FAIL — 404 (rota inexistente).

- [ ] **Step 3: Adicionar o endpoint** (em `src/api/routes/extracao.py`, após `status_lote`)

```python
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/lote/{job_uuid}/excel", summary="Download do Excel consolidado do lote")
def download_excel_lote(job_uuid: str, db: Session = Depends(get_db)):
    job = db.scalar(select(LoteJob).where(LoteJob.job_uuid == job_uuid))
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if job.status == StatusLote.FALHOU:
        raise HTTPException(status_code=422, detail=job.erro_detalhe or "Processamento falhou.")
    if job.status != StatusLote.CONCLUIDO or not job.excel_path:
        raise HTTPException(status_code=409, detail="Lote ainda em processamento.")
    return FileResponse(job.excel_path, media_type=_XLSX_MIME,
                        filename=Path(job.excel_path).name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_lote_endpoints.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/extracao.py tests/test_lote_endpoints.py
git commit -m "feat(fase3): GET /lote/{uuid}/excel download (200/409/422/404)"
```

---

## Task 5: Worker `processar_job` (núcleo)

**Files:**
- Create: `scripts/worker_lote.py`
- Test: `tests/test_worker_lote.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worker_lote.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_worker_lote.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.worker_lote`.

- [ ] **Step 3: Criar o worker (núcleo)**

```python
# scripts/worker_lote.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_worker_lote.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/worker_lote.py tests/test_worker_lote.py
git commit -m "feat(fase3): worker processar_job (PDF a PDF, falha parcial isolada)"
```

---

## Task 6: Worker — claim atômico, reset de órfão e loop

**Files:**
- Modify: `scripts/worker_lote.py`

- [ ] **Step 1: Adicionar claim, reset e loop** (no fim de `scripts/worker_lote.py`)

```python
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
```

- [ ] **Step 2: Verificar import (smoke)**

Run: `python -c "import scripts.worker_lote as w; print(w.executar_worker, w._claim_proximo, w._resetar_orfaos)"`
Expected: imprime as 3 funções sem erro.

- [ ] **Step 3: Garantir suíte de worker ainda verde**

Run: `python -m pytest tests/test_worker_lote.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/worker_lote.py
git commit -m "feat(fase3): worker claim SKIP LOCKED + reset de orfao + loop/--once"
```

---

## Task 7: Prova e2e auto-limpante (banco real)

**Files:**
- Create: `scripts/prova_lote_async.py`

- [ ] **Step 1: Criar a prova**

```python
# scripts/prova_lote_async.py
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
```

- [ ] **Step 2: Rodar a prova (precisa do PostgreSQL de teste no ar)**

Run: `python scripts/prova_lote_async.py`
Expected: termina com `RESULTADO: PASSOU` e remove o staging/job criado.

- [ ] **Step 3: Commit**

```bash
git add scripts/prova_lote_async.py
git commit -m "test(fase3): prova e2e auto-limpante do lote assincrono"
```

---

## Task 8: Ajustar workflow n8n (POST → polling via retry → download)

**Files:**
- Modify: `n8n_workflows/workflow_upload_pcmso.json`

- [ ] **Step 1: Substituir o conteúdo do arquivo**

```json
{
  "name": "PCMSO - Lote assíncrono (Excel para revisão)",
  "_nota": "Fase 3: POST /extrair-lote agora é assíncrono e devolve {job_uuid}. O download em GET /lote/{job_uuid}/excel responde 409 enquanto processa; o nó de download usa Retry On Fail (polling) até o worker concluir. Garanta que o worker está rodando (scripts/worker_lote.py em loop, ou um cron chamando --once). Ajuste host/porta conforme o deploy.",
  "nodes": [
    {
      "parameters": { "rule": { "interval": [{ "field": "cronExpression", "expression": "0 7 1 * *" }] } },
      "id": "trigger-mensal",
      "name": "Gatilho mensal (1o dia 07h)",
      "type": "n8n-nodes-base.scheduleTrigger",
      "position": [240, 300]
    },
    {
      "parameters": { "fileSelector": "data/pcmso_raw/*.pdf", "options": {} },
      "id": "read-pdfs",
      "name": "Ler PDFs da pasta",
      "type": "n8n-nodes-base.readWriteFile",
      "position": [460, 300]
    },
    {
      "parameters": {
        "url": "http://localhost:8000/extrair-lote",
        "method": "POST",
        "sendBody": true,
        "contentType": "multipart-form-data",
        "bodyParameters": {
          "parameters": [
            { "parameterType": "formBinaryData", "name": "files", "inputDataFieldName": "data" }
          ]
        },
        "options": {}
      },
      "id": "http-extrair-lote",
      "name": "Extrair Lote (cria job)",
      "type": "n8n-nodes-base.httpRequest",
      "position": [680, 300]
    },
    {
      "parameters": {
        "url": "=http://localhost:8000/lote/{{ $json.job_uuid }}/excel",
        "method": "GET",
        "options": {
          "response": { "response": { "responseFormat": "file" } },
          "retryOnFail": true,
          "maxTries": 20,
          "waitBetweenTries": 30000
        }
      },
      "id": "http-download-excel",
      "name": "Baixar Excel (polling via retry)",
      "type": "n8n-nodes-base.httpRequest",
      "position": [900, 300]
    },
    {
      "parameters": {
        "operation": "write",
        "fileName": "data/pcmso_lote/PCMSO_Lote_{{ $now.format('yyyy-MM-dd') }}.xlsx",
        "dataPropertyName": "data",
        "options": {}
      },
      "id": "save-excel",
      "name": "Salvar Excel p/ analista",
      "type": "n8n-nodes-base.readWriteFile",
      "position": [1120, 300]
    },
    {
      "parameters": {
        "jsCode": "return [{ json: { tipo: 'lote_pronto', mensagem: 'Lote extraído (assíncrono). Revise o Excel (aba Metadados traz status de duplicata/versão) e suba em /converter-excel.' } }];"
      },
      "id": "fn-notif-lote",
      "name": "Notificar - Lote pronto",
      "type": "n8n-nodes-base.code",
      "position": [1340, 300]
    }
  ],
  "connections": {
    "Gatilho mensal (1o dia 07h)": { "main": [[{ "node": "Ler PDFs da pasta", "type": "main", "index": 0 }]] },
    "Ler PDFs da pasta":          { "main": [[{ "node": "Extrair Lote (cria job)", "type": "main", "index": 0 }]] },
    "Extrair Lote (cria job)":    { "main": [[{ "node": "Baixar Excel (polling via retry)", "type": "main", "index": 0 }]] },
    "Baixar Excel (polling via retry)": { "main": [[{ "node": "Salvar Excel p/ analista", "type": "main", "index": 0 }]] },
    "Salvar Excel p/ analista":   { "main": [[{ "node": "Notificar - Lote pronto", "type": "main", "index": 0 }]] }
  }
}
```

- [ ] **Step 2: Validar JSON**

Run: `python -c "import json; json.load(open('n8n_workflows/workflow_upload_pcmso.json', encoding='utf-8')); print('json ok')"`
Expected: `json ok`.

- [ ] **Step 3: Commit**

```bash
git add n8n_workflows/workflow_upload_pcmso.json
git commit -m "chore(fase3): n8n workflow usa POST->polling(retry)->download"
```

---

## Task 9: Atualizar o manual do administrador

**Files:**
- Modify: `pcmso-alert-system/docs/manual_admin.md`

- [ ] **Step 1: Seção 8 — registrar a entrega da Fase 3**

Após o bloco da Fase 2, adicionar:

```markdown
**Fase 3 — ingestão assíncrona de lotes grandes** (50–300 PDFs): `POST /extrair-lote`
agora é assíncrono — devolve `job_uuid` (HTTP 202) e grava os PDFs em staging
(`PCMSO_LOTE_STAGING`). Um worker (`scripts/worker_lote.py`) processa PDF a PDF,
com progresso em `GET /lote/{uuid}` e download em `GET /lote/{uuid}/excel` (409
enquanto processa, 422 se falhou). Fila na tabela nova `lote_jobs` (estados
`pendente/processando/concluido/falhou`); claim com `FOR UPDATE SKIP LOCKED`;
jobs órfãos resetam para `pendente` no start do worker. n8n ajustado para
POST→polling(retry)→download. Prova: `scripts/prova_lote_async.py`.
```

- [ ] **Step 2: Seção 9 — gotcha novo do polling/worker**

Adicionar ao final da lista de gotchas:

```markdown
- **"Subi o lote e o Excel não baixa"** → o processamento é assíncrono; cheque
  `GET /lote/{uuid}` (status/progresso). Se ficar `pendente` parado, o **worker
  não está rodando** — suba `scripts/worker_lote.py` (loop) ou o cron `--once`.
  `409` = ainda processando; `422` = `falhou` (veja `erro_detalhe`).
```

- [ ] **Step 3: Seção 11 — remover "Fase 3 — escala" e anotar novas pendências**

Remover a linha `- **Fase 3** — escala (...)`. Acrescentar:

```markdown
- **Limpeza de staging/Excel** — `lote_jobs` e `PCMSO_LOTE_STAGING` crescem
  indefinidamente; falta uma rotina de retenção/TTL.
- **Throughput intra-lote** — o worker processa PDFs sequencialmente; paralelizar
  por job ficou fora do escopo da Fase 3.
```

- [ ] **Step 4: Commit**

```bash
git add pcmso-alert-system/docs/manual_admin.md
git commit -m "docs(fase3): manual do admin atualizado (secoes 8, 9, 11)"
```

---

## Task 10: Verificação final

- [ ] **Step 1: Suíte completa verde (DB-free)**

Run: `python -m pytest -q`
Expected: todos passam (78 anteriores + novos de `tests/test_lote_*` e `tests/test_worker_lote.py`).

- [ ] **Step 2: Prova e2e (banco de teste no ar)**

Run: `python scripts/prova_lote_async.py`
Expected: `RESULTADO: PASSOU`.

- [ ] **Step 3: Regressão das provas da Fase 2**

Run: `python scripts/prova_upsert_cnpj.py && python scripts/prova_guard_duplicata.py`
Expected: ambas `PASSOU` (o endpoint de aprovação não foi tocado).

- [ ] **Step 4: Commit final (se houver ajuste pendente)**

```bash
git add -A
git commit -m "chore(fase3): verificacao final do lote assincrono"
```

---

## Self-Review (preenchido)

**Cobertura da spec:** §2 modelo → Task 1; §3 endpoints (POST/GET status/GET excel + env) → Tasks 2–4; §4 worker (processar_job, claim SKIP LOCKED, --once/loop, reset órfão) → Tasks 5–6; §5 testes (unit + e2e auto-limpante, golden-files intactos, sem SQLite) → Tasks 2–7 e 10; §6 entregáveis (n8n + manual) → Tasks 8–9; §7 fora de escopo → registrado na Task 9 (seção 11 do manual). Sem lacunas.

**Placeholders:** nenhum — todo passo tem código/comando reais.

**Consistência de tipos:** `StatusLote.{PENDENTE,PROCESSANDO,CONCLUIDO,FALHOU}` e os campos de `LoteJob` (`job_uuid`, `processados`, `com_erro`, `staging_dir`, `excel_path`, `erro_detalhe`, `finished_at`) usados de forma idêntica em endpoints, worker e testes. `processar_job`/`_claim_proximo`/`_resetar_orfaos`/`executar_worker` com assinaturas consistentes entre worker e provas/testes. `gerar_excel(resultados) -> bytes` e `erros_extracao` conforme o `excel_builder` atual.
