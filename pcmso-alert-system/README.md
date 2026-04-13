# PCMSO Alert System

Sistema de automação de alertas de exames ocupacionais baseado em documentos PCMSO.

## Visão Geral

- **Extração** de dados de PDFs PCMSO (colaboradores, exames, mapeamentos cargo×risco×exame)
- **Validação técnica** via interface web antes de importar para o banco
- **Gestão de demandas** — técnico informa empresa + colaborador + cargo → sistema gera exames automaticamente
- **Alertas diários** (D+10 a D+15) via Gmail e WhatsApp (Evolution API)
- **Dashboard** por empresa com métricas, gráficos e exportação
- **Relatório mensal** automático em PDF e Excel

---

## Requisitos

- Python 3.10+
- PostgreSQL 15+ (ou Docker)
- n8n (via Docker)
- Evolution API instalada e configurada (para WhatsApp)
- Conta Google com Gmail API habilitada

---

## Setup Rápido

### 1. Clonar e instalar dependências

```bash
cd D:\vinic\prj_2R\pcmso-alert-system
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
# Edite .env com suas credenciais
```

### 3. Subir PostgreSQL e n8n com Docker

```bash
docker-compose up -d
# Aguarde o healthcheck do PostgreSQL (~15 segundos)
```

### 4. Criar schema do banco

```bash
python scripts/init_database.py
```

### 5. Popular com dados de teste

```bash
python scripts/seed_test_data.py
```

---

## Executando os Serviços

### Interface de Validação + API (FastAPI)

```bash
uvicorn src.validation_interface.web_validator:app --reload --port 5000
```

Acesse:
- `http://localhost:5000/validacao` — Fila de validação técnica
- `http://localhost:5000/demandas/` — Demandas de movimentações
- `http://localhost:5000/colaboradores/` — Gestão de colaboradores
- `http://localhost:5000/docs` — Documentação automática da API

### Dashboard Streamlit (Empresas)

```bash
streamlit run src/dashboard/app.py
```

Acesse `http://localhost:8501` e faça login com as credenciais do seed:
- **MetalSP**: CNPJ `12.345.678/0001-90` | Senha `senha123`
- **ConstNorte**: CNPJ `98.765.432/0001-10` | Senha `senha123`

---

## Configurar Gmail API

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto → Habilite Gmail API
3. Crie credenciais OAuth2 (Aplicativo Desktop)
4. Baixe o `credentials.json` e salve em `config/gmail_credentials.json`
5. Na primeira execução, o browser abrirá para autorização

---

## Configurar Evolution API (WhatsApp)

```bash
# Instalar Evolution API (Docker)
docker run -d --name evolution_api -p 8080:8080 \
  -e AUTHENTICATION_API_KEY=sua_chave_aqui \
  atendai/evolution-api:latest

# Criar instância e escanear QR Code
# Acesse http://localhost:8080 e crie a instância "pcmso_instance"
```

No `.env`:
```env
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=sua_chave_aqui
EVOLUTION_INSTANCE=pcmso_instance
```

---

## Importar Workflows n8n

1. Acesse `http://localhost:5678` (admin/admin123)
2. Menu → **Import from file**
3. Importe os 3 arquivos de `n8n_workflows/`:
   - `workflow_daily_alerts.json` — Alertas diários às 05:00
   - `workflow_upload_pcmso.json` — Watch folder de PDFs
   - `workflow_monthly_report.json` — Relatório mensal no dia 1

---

## Fluxo Completo

### Ingestão de PCMSO
```
1. Salvar PDF em data/pcmso_raw/
2. n8n detecta → aciona /api/extrair-pcmso
3. Sistema extrai e move para data/pcmso_pending_validation/
4. Técnico recebe notificação
5. Acessa http://localhost:5000/validacao
6. Revisa, corrige se necessário, clica Aprovar
7. Dados importados para PostgreSQL
```

### Gestão de Demandas
```
1. Técnico acessa http://localhost:5000/demandas/nova
2. Seleciona empresa → colaborador → cargo → tipo (admissional/periódico/demissional)
3. Sistema consulta cargo_exames e gera exames automaticamente
4. Para admissional: preenche dados do novo colaborador na mesma tela
5. Para demissional: colaborador é inativado automaticamente
```

### Gestão de Colaboradores (interface planilha)
```
1. Acessa http://localhost:5000/colaboradores/?empresa_id=1
2. Edita dados diretamente na tabela (clica no campo → edita → Salvar)
3. Adiciona novo: clica "Novo Colaborador" → preenche linha → Salvar
4. Inativa (demissão): clica ícone de pessoa com "-" na linha
```

### Alertas Diários
```
Todo dia às 05:00 → n8n aciona /api/processar-alertas
→ Busca exames vencendo em D+10 a D+15
→ Agrupa por empresa
→ Envia email HTML + WhatsApp por empresa
→ Registra histórico em alertas_enviados
```

---

## Testes

```bash
pytest tests/ -v

# Testes específicos
pytest tests/test_extraction.py -v     # Validação CNPJ/CPF/datas
pytest tests/test_alerts.py -v        # Motor de alertas e prazos
pytest tests/test_communications.py -v # Gmail/WhatsApp (com mocks)
```

---

## Estrutura do Projeto

```
pcmso-alert-system/
├── config/              # Database, Gmail, WhatsApp
├── src/
│   ├── database/        # Models (9 tabelas), queries
│   ├── extraction/      # PDF extractor, validators, duplicate checker
│   ├── demandas/        # Gestão de demandas e colaboradores
│   ├── validation_interface/  # FastAPI + templates HTML
│   ├── business_logic/  # Alert engine, mensagens, relatórios
│   ├── communications/  # Gmail API, Evolution API (WhatsApp)
│   └── dashboard/       # Streamlit multi-página
├── n8n_workflows/       # 3 workflows prontos para importar
├── scripts/             # init_database, seed, run_extraction
├── tests/               # pytest (extraction, alerts, communications)
└── data/                # pcmso_raw/, pcmso_pending_validation/, pcmso_processed/
```

---

## Variáveis de Ambiente Obrigatórias

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | URL do PostgreSQL |
| `GMAIL_CREDENTIALS_FILE` | Caminho do credentials.json do Google |
| `GMAIL_SENDER_EMAIL` | Email remetente |
| `EVOLUTION_API_URL` | URL da Evolution API |
| `EVOLUTION_API_KEY` | Chave de autenticação |
| `EVOLUTION_INSTANCE` | Nome da instância WhatsApp |
| `SECRET_KEY` | Chave secreta da aplicação |
