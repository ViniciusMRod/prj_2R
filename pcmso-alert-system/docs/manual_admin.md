# Manual do Administrador — PCMSO Alert System

> Documento de referência para o desenvolvedor/administrador da ferramenta.
> Cobre o que cada parte faz, os fluxos de ponta a ponta, as armadilhas de
> produção e os scripts de diagnóstico. Mantenha atualizado a cada fase.

---

## 1. O problema que a ferramenta resolve

Empresas clientes têm um **PCMSO** (Programa de Controle Médico de Saúde
Ocupacional) — documento legal anual que define **quais exames cada cargo é
obrigado a fazer e com que periodicidade**. A ferramenta automatiza três coisas:

1. **Lê o PCMSO em PDF** e o transforma em dados estruturados (cargo → exames).
2. **Gera exames automaticamente** em movimentações de colaborador (admissão,
   demissão, retorno, etc.).
3. **Avisa o SSO** (Serviço de Saúde Ocupacional de cada empresa) quando há
   exames vencendo.

O ponto central é a tabela **`cargo_exames`**: é o "contrato" extraído do PCMSO
que alimenta os outros dois fluxos.

---

## 2. Stack

- **Python + FastAPI** — API e interface web de validação (`web_validator.py`, `api/`).
- **SQLAlchemy + PostgreSQL** — 10 tabelas (`database/models.py`).
- **openpyxl** — geração/leitura do Excel de revisão.
- **pypdf** — leitura dos PDFs.
- **Streamlit** — dashboard das empresas (`dashboard/app.py`).
- **n8n** — agendador externo que dispara os fluxos cron (alertas diários,
  relatório mensal, upload). O n8n apenas agenda/chama; a lógica está no Python.

---

## 3. Modelo de dados — as 10 tabelas (o coração)

| Tabela | Papel | Chave/constraint a conhecer |
|---|---|---|
| `empresas` | Cliente. Tem e-mail/WhatsApp do SSO. | `cnpj` **unique** (gravado **com máscara** `XX.XXX.XXX/XXXX-XX`) |
| `colaboradores` | Pessoas da empresa | `cpf` **unique** (com máscara) |
| `tipos_exames` | **Catálogo** de exames (Hemograma, Audiometria…) | `nome_normalizado` **unique** — chave de convergência |
| `exames` | Exame concreto de um colaborador, com `data_proximo_exame` | índices em data e status |
| `alertas_enviados` | Histórico de notificações (1 por empresa/canal/dia) | — |
| `validacao_pendente` | Fila de PCMSOs aguardando o técnico; guarda `dados_extraidos` (JSONB) | — |
| `pcmso_versoes` | Versionamento dos PCMSOs por empresa/ano | `hash_arquivo` **unique** + `uq_pcmso_versao(empresa,ano,versao)` |
| `cargo_exames` | **Cargo → exame obrigatório** (o contrato) | `uq_cargo_exame(empresa,cargo,tipo_exame)` |
| `demandas` | Movimentação registrada pelo técnico; snapshot dos exames gerados | — |
| `lote_jobs` | Fila de jobs de ingestão assíncrona de PDFs (Fase 3) | `job_uuid` **unique**; índice `(status, created_at)` |

> **Três `unique` que causam a maioria dos erros de produção:**
> `empresas.cnpj`, `pcmso_versoes.hash_arquivo` e
> `cargo_exames(empresa,cargo,tipo_exame)`. Os bugs corrigidos na Fase 2 foram
> exatamente colisões nesses três.

---

## 4. Fluxo 1 — Ingestão do PCMSO (Fases 1–3)

1. **Upload do lote** → `POST /extrair-lote` (`api/routes/extracao.py`). Desde a
   Fase 3 é **assíncrono**: grava os PDFs em staging (`PCMSO_LOTE_STAGING`), cria
   um job `pendente` em `lote_jobs` e devolve `job_uuid` (HTTP 202). Um worker
   (`scripts/worker_lote.py`) processa **PDF a PDF** em segundo plano; acompanhe
   por `GET /lote/{uuid}` e baixe o Excel em `GET /lote/{uuid}/excel`. Os passos
   2–6 abaixo rodam dentro do worker, um PDF de cada vez (não mais em paralelo na
   requisição).
2. **Extração** (`extraction/pdf_extractor.py`): regex sobre o texto puxa
   empresa, CNPJ (formatado com máscara aqui), vigência e o mapa cargo×exame da
   seção "CONTROLE MÉDICO". Filtra as linhas do prestador (Prevenclínica) para
   não poluir os dados. Calcula **score de confiança** e **hash SHA-256**.
3. **Pré-checagem de versão** (`_classificar_versionamento`): roda **sequencial**
   (a sessão SQLAlchemy não é thread-safe) e marca cada PDF como `NOVO` /
   `nova_versao` / `duplicata_exata` via `verificar_duplicata`.
4. **Excel de revisão** (`extraction/excel_builder.py`): gera `.xlsx` com
   **5 abas de dados** (Empresas, Cargos, Riscos, Exames, Cargo_Exames) +
   **Metadados** (hash, status) + **Erros**. O analista humano confere e corrige.
5. **Volta do Excel** (`excel_converter.py`): o round-trip preserva o `hash`
   (Fase 1) — é assim que o sistema sabe que o arquivo aprovado é o mesmo que foi
   extraído.
6. **Aprovação** → `POST /validacao/{id}/aprovar` (`web_validator.py`). Grava no
   banco em passos numerados:
   - **Passo 0 (guard de duplicata — Fase 2 item 3):** se o `hash` já existe em
     `pcmso_versoes`, **não grava nada** e devolve aviso amigável.
   - **Passo 1 (upsert da empresa — Fase 2 item 2):** busca e insere usando
     `formatar_cnpj(cnpj)` (forma mascarada canônica).
   - **Passos 3–4:** insere colaboradores e o mapa `cargo_exames` (com dedup em
     memória, porque `autoflush=False`).
   - **Passo 6:** `registrar_versao` grava em `pcmso_versoes` (calcula v1, v2…).

---

## 5. Fluxo 2 — Demandas (`demandas/demand_manager.py`)

Quando um técnico registra uma movimentação (`gerar_demanda`):

1. Consulta `cargo_exames` da empresa para aquele cargo (`get_exames_por_cargo`).
2. Para cada exame obrigatório, cria um `Exame` com `data_proximo_exame`
   calculada pelo **tipo de movimentação**:
   - Admissional / Demissional / Retorno / Mudança de função → exame **imediato**.
   - Periódico → hoje + periodicidade.
3. Calcula o **prazo** (`PRAZOS_MOVIMENTACAO`): admissional D+7, demissional D+3,
   retorno D+1, mudança D+15, periódico D+30.
4. Se o cargo **não tem mapeamento**, devolve aviso ("verifique o mapeamento ou
   adicione manualmente") — não falha.

> Sem `cargo_exames` populado pelo Fluxo 1, a demanda não gera exame nenhum.

---

## 6. Fluxo 3 — Alertas diários (`business_logic/alert_engine.py`)

Disparado pelo n8n às **05h00** (`processar_alertas_diarios`):

1. Marca exames vencidos.
2. Busca exames vencendo na janela **D+10 a D+15**.
3. Agrupa por empresa.
4. Para cada empresa, envia **e-mail + WhatsApp** ao SSO — só **1 vez por canal
   por dia** (`alerta_ja_enviado_hoje`).
5. Registra tudo em `alertas_enviados` (sucesso/falha + detalhe do erro).

---

## 7. Componentes de suporte

- **Catálogo / normalização** (`extraction/catalogo.py`): `normalizar_exame(nome)`
  devolve `(exibição, chave)`. A **chave** é casefold + sem acento + `\n`→espaço,
  e vira `tipos_exames.nome_normalizado`. É o que faz "Audiometria tonal" e
  "Audiometria Tonal" convergirem no mesmo tipo. Tem tabela `SINONIMOS` editável.
  **Decisão registrada:** fusões clínicas de Hemograma foram deixadas separadas
  de propósito.
- **Detector de duplicatas** (`duplicate_checker.py`): classifica em
  `DUPLICATA_EXATA` (mesmo hash), `NOVA_VERSAO` (mesma empresa/ano, hash
  diferente) ou `NOVO_ARQUIVO`.
- **Score de confiança** (`pdf_extractor.py`): calibrado nos 14 PDFs reais
  (14× ALTA). Pesa campos críticos (CNPJ e vigência valem mais).
- **Dashboard** (`dashboard/app.py`): login da empresa por CNPJ + senha (bcrypt),
  só leitura dos próprios dados.
- **n8n** (`n8n_workflows/`): `workflow_upload_pcmso`, `workflow_daily_alerts`,
  `workflow_monthly_report`, `workflow_limpeza_staging`. **Dois apps, duas portas:**
  os endpoints `/extrair-lote` e `/lote/{uuid}*` são da API de extração na
  **porta 8000** (`src.api.main`); `/api/processar-alertas` e
  `/api/relatorio-mensal` são do `web_validator` na **porta 5000**. Cada workflow
  traz um `_nota` com a porta/app correto — **não unifique as portas**.
  - `workflow_upload_pcmso`: dois gatilhos (cron mensal + webhook manual
    `POST /webhook/upload-pcmso-lote`); acompanha o job por **polling explícito**
    (`GET /lote/{uuid}` → IFs `concluido`/`falhou`/loop), não mais por `retryOnFail`.
  - `workflow_limpeza_staging`: cron semanal (segunda 04h) → `executeCommand`
    `python scripts/worker_lote.py --limpar`. Precisa rodar no host do app; se o
    n8n estiver em container separado, use cron de sistema ou um endpoint.

---

## 8. O que foi entregue, por fase (com commits)

**Fase 1 — versionamento** (`ea15744`): o `hash` passa a sobreviver ao round-trip
do Excel, ligando o arquivo extraído ao arquivo aprovado.

**Fase 2 — robustez da ingestão** (ordem 4→1→2→3, concluída em 2026-06-13):

- **Item 4 — golden-files** (`6600ca1`): `tests/test_golden_files.py` congela a
  saída de `extrair_pcmso` dos 14 PDFs. (Goldens ficam locais, fora do git por
  LGPD.)
- **Item 1 — normalização do catálogo** (`120bcea`): normalização vive **na
  gravação**, não no extrator (para não invalidar os goldens). Catálogo
  convergiu de 41→39 tipos.
- **Item 2 — upsert de CNPJ** (`ab5792b`): busca e INSERT da empresa usam
  `formatar_cnpj`. **Antes:** a busca removia a máscara mas o banco grava com
  máscara → reaprovar a mesma empresa estourava `empresas_cnpj_key` (erro 500).
- **Item 3 — guard de duplicata** (`cad196f`): aprovar o mesmo PDF 2× estourava
  `IntegrityError` no `hash_arquivo`. **Agora:** vira aviso amigável na tela, sem
  tocar no banco.

**Fase 3 — ingestão assíncrona de lotes grandes** (50–300 PDFs): `POST /extrair-lote`
agora é assíncrono — devolve `job_uuid` (HTTP 202) e grava os PDFs em staging
(`PCMSO_LOTE_STAGING`). Um worker (`scripts/worker_lote.py`) processa PDF a PDF,
com progresso em `GET /lote/{uuid}` e download em `GET /lote/{uuid}/excel` (409
enquanto processa, 422 se falhou). Fila na tabela nova `lote_jobs` (estados
`pendente/processando/concluido/falhou`); claim com `FOR UPDATE SKIP LOCKED`;
jobs órfãos resetam para `pendente` no start do worker. n8n ajustado para
POST→polling(retry)→download. Prova: `scripts/prova_lote_async.py`.

**Limpeza de staging/TTL** (`worker_lote.py --limpar`): remove `staging_dir` de
jobs terminais mais antigos que o TTL (padrão 7 dias, env `PCMSO_LOTE_TTL_DIAS` ou
flag `--ttl`). Mantém o registro `lote_jobs` para auditoria; zera `staging_dir` e
`excel_path` no banco para sinalizar que os arquivos foram limpos. 95 testes.

---

## 9. Gotchas para o suporte em produção

- **"Reaprovei e deu erro"** → era o item 2/3, já corrigido. Se reaparecer, é
  colisão em `cnpj` ou `hash_arquivo`.
- **"Importei o PCMSO mas a demanda não gera exame"** → `cargo_exames` da empresa
  está vazio para aquele cargo, ou o nome do cargo difere.
- **"O exame X e Y deviam ser o mesmo"** → tabela `SINONIMOS` no `catalogo.py`;
  convergência é por `nome_normalizado`.
- **"Não recebi alerta"** → janela é D+10 a D+15 apenas; há trava de 1 envio por
  canal/dia; cheque `alertas_enviados`.
- **CNPJ é sempre mascarado no banco.** Toda busca nova deve usar `formatar_cnpj`
  dos dois lados.
- **"Subi o lote e o Excel não baixa"** → o processamento é assíncrono; cheque
  `GET /lote/{uuid}` (status/progresso). Se ficar `pendente` parado, o **worker
  não está rodando** — suba `scripts/worker_lote.py` (loop) ou o cron `--once`.
  `409` = ainda processando; `422` = `falhou` (veja `erro_detalhe`).
- **"O workflow de alertas/relatório dá connection refused"** → esses endpoints
  estão no `web_validator` (**porta 5000**), não na API de extração (8000). Cada
  workflow tem um `_nota` com a porta certa; **não troque 5000 por 8000**.
- **"O workflow de limpeza não roda"** → o nó `executeCommand` exige que o n8n
  esteja no mesmo host do app, com `cwd` na raiz do projeto e o Python no PATH. Em
  container separado, troque por cron de sistema ou um endpoint HTTP.
- **"GET /lote/{uuid}/excel retornou 404 depois de um tempo"** → o job expirou o
  TTL e a limpeza já removeu os arquivos. O registro ainda existe no banco com
  `staging_dir=null`; o Excel não está mais disponível.

---

## 10. Guia de subida dos serviços (pré-requisito para rodar no n8n)

Antes de importar os workflows no n8n e testar com dados reais, todos os 4 componentes abaixo precisam estar de pé **no mesmo host** (ou com os hosts ajustados nos JSONs).

### Sequência de subida (4 terminais / processos)

```powershell
# 1 — API de extração (porta 8000) — gateway dos workflows de upload
cd D:\vinic\prj_2R\pcmso-alert-system
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 2 — Web validator (porta 5000) — alertas diários + relatório mensal
uvicorn src.validation_interface.web_validator:app --host 0.0.0.0 --port 5000 --reload

# 3 — Worker de lote (loop contínuo) — processa a fila lote_jobs
python scripts/worker_lote.py

# 4 — Dashboard Streamlit (opcional, porta 8501)
streamlit run dashboard/app.py
```

> Se preferir `--once` no worker (para usar com cron ou n8n `executeCommand`), substitua o comando 3 por `python scripts/worker_lote.py --once`.

### Ajuste de host para n8n em Docker

Os JSONs dos workflows usam `http://localhost:800x`. Se o n8n rodar em container separado, substitua `localhost` por `host.docker.internal` nos 4 arquivos de `n8n_workflows/` antes de importar.

### Passos para importar os workflows no n8n

1. Abra o n8n editor.
2. Menu → **Workflows** → **Import from file**.
3. Importe cada um dos 4 JSONs de `n8n_workflows/` em qualquer ordem.
4. Ative manualmente cada workflow (toggle ativo).
5. Para testar o upload sem esperar o cron mensal: dispare o webhook `POST /webhook/upload-pcmso-lote` com os PDFs do analista em `multipart/form-data` (campo `files`).

### Validação mínima antes do lote real

```powershell
# Backend isolado (sem n8n) — deve imprimir "RESULTADO: PASSOU"
python scripts/prova_lote_async.py

# Health dos dois apps (depois de subir os serviços)
curl http://localhost:8000/docs   # deve abrir a UI Swagger da extração
curl http://localhost:5000/docs   # deve abrir a UI Swagger do web_validator
```

### Onde colocar os PDFs do analista

- Pasta de entrada: `data/pcmso_raw/` (configure `PCMSO_PDF_DIR` no `.env` se quiser outro caminho).
- Pasta de saída (Excel gerado): `data/pcmso_lote/` (criada em 2026-06-16).

---

## 11. Scripts de diagnóstico

- `scripts/raio_x_banco.py` — inspeção **read-only** do PostgreSQL (use `--detalhe`).
- `scripts/e2e_lote_demo.py` — prova o fluxo de ingestão ponta a ponta.
- `scripts/prova_upsert_cnpj.py` e `scripts/prova_guard_duplicata.py` — provas
  auto-limpantes dos fixes da Fase 2 (rodam contra o banco de teste e o deixam
  limpo).
- `scripts/worker_lote.py` — worker que processa a fila `lote_jobs` (`--once` para o n8n cron, ou loop contínuo); `--limpar [--ttl DIAS]` para limpeza de staging.
- `scripts/prova_lote_async.py` — prova e2e auto-limpante do lote assíncrono.
- Suíte: `python -m pytest -q` → **95 testes**.

---

## 12. O que ainda falta (fora de escopo até agora)

- **Fase 4** — e2e formal automatizado.
- **Throughput intra-lote** — o worker processa PDFs sequencialmente; paralelizar
  por job ficou fora do escopo da Fase 3.
- **Colaboradores no lote** — hoje o round-trip do Excel **não** carrega lista de
  pessoas (elas entram pelo fluxo de demanda). Falta confirmar se é o modelo
  definitivo.
- **Admin/ambientes** — gestão de usuários técnicos, ambientes de produção.

---

> **Contexto atual:** **fase de testes, sem dados reais** — o banco é descartável
> e os PDFs são exemplos. Antes de produção, a seção 9 (gotchas) é o que mais
> gera dúvida de usuário.
