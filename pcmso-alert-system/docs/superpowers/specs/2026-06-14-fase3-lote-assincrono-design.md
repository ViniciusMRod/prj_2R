# Fase 3 — Ingestão assíncrona de lotes grandes de PDFs

**Data:** 2026-06-14
**Status:** Design aprovado (brainstorming) — pronto para plano de implementação.
**Pré-requisito:** Fase 2 completa (78 testes verdes, working tree limpo).

---

## 1. Problema e objetivo

Hoje `POST /extrair-lote` (`src/api/routes/extracao.py`) processa os PDFs de forma
**síncrona** dentro da requisição HTTP (`ThreadPoolExecutor`, até 8 workers) e
devolve o `.xlsx` na resposta. Com lotes grandes isso fura: **timeout HTTP,
estouro de memória e falha total se um PDF quebra**.

**Objetivo da Fase 3:** suportar com folga lotes de **50 a 300 PDFs** tornando a
ingestão **assíncrona**: a requisição aceita o lote e devolve um identificador; o
processamento ocorre em segundo plano, PDF a PDF, com progresso consultável e
resultado disponível para download quando pronto.

**Restrição firme:** **zero dependência nova** (sem Redis/Celery). Fila de jobs na
própria base PostgreSQL + um worker. Alinhado ao CLAUDE.md (não adicionar
dependências sem justificar) e à fase de testes atual.

### Decisões fechadas no brainstorming (respostas do usuário)

- Foco: **lote grande de PDFs**.
- Volume-alvo: **50 a 300** PDFs por lote.
- Infra: **zero dependência nova** (tabela de jobs no Postgres + worker).
- Arquitetura: **abordagem A** — worker como processo separado, por polling.
- Estados terminais: **`concluido` e `falhou`** apenas (sem `concluido_com_erros`;
  o contador `com_erro > 0` sinaliza "olhar a aba Erros").
- Progresso: **polling** (cliente/n8n consulta o status). Sem webhook.
- Mudança de contrato do `/extrair-lote`: **aprovada**.
- Recuperação de job órfão: **reset simples no start** do worker.
- Limpeza de arquivos (staging/Excel): **fora do escopo** desta fase.

---

## 2. Modelo de dados

### Nova tabela `lote_jobs` (10ª tabela, `src/database/models.py`)

| Coluna | Tipo | Papel |
|---|---|---|
| `id` | int PK autoincrement | chave interna |
| `job_uuid` | String(36) unique, not null, index | id público na URL (`/lote/{uuid}`) |
| `status` | Enum `StatusLote` | máquina de estados (abaixo) |
| `total_pdfs` | int not null | total de PDFs do lote |
| `processados` | int not null default 0 | progresso (incrementa por PDF) |
| `com_erro` | int not null default 0 | quantos PDFs falharam na extração |
| `staging_dir` | String(500) not null | pasta com os PDFs do lote |
| `excel_path` | String(500) nullable | caminho do `.xlsx` gerado (ao concluir) |
| `erro_detalhe` | Text nullable | mensagem quando `status=falhou` |
| `created_at` | DateTime server_default now() | auditoria |
| `updated_at` | DateTime server_default now(), onupdate now() | heartbeat de progresso |
| `finished_at` | DateTime nullable | quando atingiu estado terminal |

### Enum `StatusLote` (str, enum.Enum)

```
pendente    -> criado pelo endpoint; nenhum worker assumiu
processando -> um worker assumiu o job
concluido   -> processamento terminou (pode ter com_erro > 0)
falhou      -> erro sistêmico antes/durante (erro_detalhe explica)
```

Transições válidas:
`pendente → processando → {concluido | falhou}`
e, na recuperação de órfão: `processando → pendente` (reset no start).

**Notas de design:**
- `job_uuid` desacopla o id público da PK sequencial.
- Não há estado `concluido_com_erros`: o status terminal de sucesso é sempre
  `concluido`; quem precisa saber se houve falha parcial olha `com_erro`.
- Migração: criar a tabela. Em fase de testes o banco é descartável
  (`drop_all`/`create_all` via `scripts/init_database.py`); não é necessária
  migração Alembic formal nesta fase.

---

## 3. Contrato dos endpoints (`src/api/routes/extracao.py`)

### `POST /extrair-lote` (comportamento alterado: síncrono → assíncrono)

- Entrada: N PDFs via `multipart/form-data` (igual a hoje).
- Ação: salva cada PDF em `PCMSO_LOTE_STAGING/{job_uuid}/`; cria registro
  `lote_jobs` (`status=pendente`, `total_pdfs=N`, `staging_dir=...`).
- Resposta: **HTTP 202** com
  `{"job_uuid": "...", "total_pdfs": N, "status": "pendente"}`.
- Não processa PDF na requisição.
- Erro: nenhum arquivo enviado → **HTTP 400**.

### `GET /lote/{job_uuid}` (status/progresso — alvo do polling)

```json
{
  "job_uuid": "...",
  "status": "processando",
  "total_pdfs": 120,
  "processados": 47,
  "com_erro": 2,
  "excel_pronto": false
}
```
- `excel_pronto` = `status == "concluido"`.
- uuid inexistente → **HTTP 404**.

### `GET /lote/{job_uuid}/excel` (download do resultado)

- `status=concluido` → devolve o `.xlsx` (5 abas de dados + Metadados + Erros,
  idêntico ao Excel atual de `gerar_excel`).
- `status` em `pendente`/`processando` → **HTTP 409** ("lote ainda em
  processamento").
- `status=falhou` → **HTTP 422** com `erro_detalhe`.
- uuid inexistente → **HTTP 404**.

### Configuração

Nova env `PCMSO_LOTE_STAGING` (default `data/pcmso_lote_staging/`), no mesmo
padrão de `PCMSO_RAW_PATH` / `PCMSO_PENDING_PATH` / `PCMSO_PROCESSED_PATH`.

### Compatibilidade

Mudança de contrato: clientes atuais (incl. n8n `workflow_upload_pcmso`) deixam de
receber o Excel direto e passam a fazer **POST → 202 → polling GET status → GET
excel**. O workflow do n8n será ajustado como parte da fase.

---

## 4. Worker (`scripts/worker_lote.py`)

### Camadas (separação para testabilidade)

- `processar_job(db, job)` — processa **um** job do início ao fim. Sem loop, sem
  polling. É a unidade testável.
- `executar_worker(once: bool, intervalo: float)` — casca: faz o claim de jobs e
  chama `processar_job`. `--once` processa os pendentes e sai (ideal para n8n
  cron); sem flag, roda em loop com `intervalo`.

### Claim atômico (padrão de fila do PostgreSQL)

```sql
SELECT ... FROM lote_jobs
WHERE status = 'pendente'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1
```
Marca `processando` e commita. Seguro mesmo com múltiplos workers (não há
dependência nova; é recurso nativo do Postgres). FIFO por `created_at`.

### Processamento PDF a PDF

Move para o worker a lógica que hoje vive no endpoint (`_processar_pdf`,
`_classificar_versionamento`, `gerar_excel`):

1. Para cada PDF em `staging_dir`:
   - `extrair_pcmso(pdf)`; em exceção, registra o erro para a aba Erros e
     incrementa `com_erro`.
   - `_classificar_versionamento(db, resultado)` (sequencial — sessão não é
     thread-safe).
   - `processados += 1`. **Commit do progresso a cada PDF** (faz o polling
     avançar).
2. Ao fim: `gerar_excel(resultados)` → grava em `excel_path` → `status=concluido`,
   `finished_at=now()`.
3. Erro sistêmico (ex.: `staging_dir` inexistente) → `status=falhou`,
   `erro_detalhe`, `finished_at=now()`.

> O paralelismo intra-lote (ThreadPoolExecutor) deixa de ser necessário para a
> robustez (o assíncrono já resolve o timeout). O processamento por PDF é
> sequencial e simples; otimização de throughput intra-job fica fora do escopo.

### Recuperação de job órfão (reset no start)

No início de `executar_worker`, todo job em `processando` volta a `pendente` e
será reprocessado. Seguro porque o processamento é idempotente: `extrair_pcmso` é
puro, `_classificar_versionamento` só lê, e o Excel é regerado do zero. Assume um
único worker (caso atual).

---

## 5. Estratégia de testes

Segue o padrão das Fases 1–2: lógica pura com fakes/monkeypatch; o que toca
Postgres usa o **banco de teste real** (JSONB é Postgres — nada de SQLite); provas
e2e auto-limpantes.

- **`processar_job` (unitário, fakes):** `pendente → concluido`; contadores
  `processados`/`com_erro` corretos; PDF que quebra incrementa `com_erro` sem
  derrubar o lote; erro sistêmico → `falhou` + `erro_detalhe`.
- **Claim atômico:** pega o `pendente` mais antigo (FIFO) e marca `processando`;
  job já `processando` não é repegado.
- **Reset de órfão:** job preso em `processando` volta a `pendente` no start.
- **Endpoints (TestClient):** `POST` → 202 + uuid; `GET status` reflete progresso;
  `GET excel` → 409 (em processamento), 200 (`concluido`), 422 (`falhou`);
  uuid inexistente → 404.
- **Prova e2e auto-limpante** `scripts/prova_lote_async.py` (irmã de
  `prova_upsert_cnpj.py` / `prova_guard_duplicata.py`): `POST` lote pequeno → roda
  worker `--once` → `GET status=concluido` → `GET excel` válido → limpa job,
  staging e Excel.
- **Sem regressão:** golden-files intactos (a extração não muda) e os 78 testes
  atuais continuam verdes.

---

## 6. Entregáveis

1. `src/database/models.py` — tabela `lote_jobs` + enum `StatusLote`.
2. `src/api/routes/extracao.py` — `POST /extrair-lote` (202), `GET /lote/{uuid}`,
   `GET /lote/{uuid}/excel`; nova env `PCMSO_LOTE_STAGING`.
3. `scripts/worker_lote.py` — `processar_job` + `executar_worker` (`--once`/loop,
   claim `SKIP LOCKED`, reset de órfão).
4. Testes unitários + de endpoint; `scripts/prova_lote_async.py`.
5. `n8n_workflows/workflow_upload_pcmso.json` — ajustado para POST→polling→download.
6. `docs/manual_admin.md` — atualizar seção 8 (entrega da Fase 3) e remover o item
   de escala da seção 11; registrar na seção 9 o novo fluxo de polling e a
   pendência de limpeza de arquivos.

---

## 7. Fora de escopo (registrar como pendências futuras)

- Limpeza automática de `staging_dir` e Excel antigos (retenção/TTL).
- Paralelismo intra-job (throughput por lote).
- Multi-worker com heartbeat por tempo (o reset no start cobre 1 worker).
- Migração Alembic formal (banco descartável na fase de testes).
- Autenticação/rate-limit dos endpoints de lote.
