# PROJETO: Sistema de Automação de Alertas de Exames Ocupacionais (PCMSO Alert System)

## CONTEXTO DO PROJETO

Você deve criar um sistema completo de automação para gerenciar alertas de exames ocupacionais com base em documentos PCMSO (Programa de Controle Médico de Saúde Ocupacional). O sistema deve:

1. Extrair dados estruturados de PDFs PCMSO
2. Validar informações com técnico especialista antes da carga no banco
3. Armazenar dados normalizados em PostgreSQL
4. Gerar alertas automáticos diários sobre exames próximos do vencimento
5. Enviar comunicações via Gmail e WhatsApp
6. Fornecer dashboards individuais para cada empresa cliente

## STACK TECNOLÓGICA OBRIGATÓRIA

- **Linguagem principal**: Python 3.10+
- **Banco de dados**: PostgreSQL 15+
- **Orquestração**: n8n (workflows e automações)
- **Extração de PDF**: pdfplumber, tabula-py (reutilizar lógica do projeto SafetyDoc AI)
- **Comunicação**: 
  - Gmail API (e-mails)
  - Evolution API ou Twilio (WhatsApp)
- **Ambiente**: Local (desenvolvimento e testes iniciais)

## ARQUITETURA DO SISTEMA

```
┌─────────────────────────────────────────────────────────────┐
│ CAMADA 1: INGESTÃO E VALIDAÇÃO                              │
│ ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐   │
│ │ Upload PCMSO│──▶│ Extração PDF │──▶│ Fila Validação  │   │
│ │   (Manual)  │   │  (Python)    │   │  (Técnico)      │   │
│ └─────────────┘   └──────────────┘   └─────────────────┘   │
│         │                                      │             │
│         │                                      ▼             │
│         │                            ┌─────────────────┐    │
│         │                            │ PostgreSQL      │    │
│         │                            │ (Dados limpos)  │    │
│         │                            └─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ CAMADA 2: PROCESSAMENTO E ALERTAS (n8n)                     │
│ ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│ │ Cron Diário  │──▶│ Motor Regras │──▶│ Gerador Msgs    │  │
│ │  (05:00 AM)  │   │ (10-15 dias) │   │ (Personalizado) │  │
│ └──────────────┘   └──────────────┘   └─────────────────┘  │
│                                                │             │
│                           ┌────────────────────┴─────┐       │
│                           ▼                          ▼       │
│                    ┌─────────────┐          ┌─────────────┐ │
│                    │ Gmail API   │          │ WhatsApp    │ │
│                    │ (Relatório) │          │ (Alertas)   │ │
│                    └─────────────┘          └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ CAMADA 3: VISUALIZAÇÃO E GESTÃO                             │
│ ┌──────────────────┐        ┌──────────────────┐            │
│ │ Dashboard Web    │        │ Relatório Mensal │            │
│ │ (por empresa)    │        │ Consolidado      │            │
│ └──────────────────┘        └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

## ESTRUTURA DO PROJETO

Crie a seguinte estrutura de diretórios e arquivos:

```
pcmso-alert-system/
│
├── README.md                          # Documentação completa do projeto
├── requirements.txt                   # Dependências Python
├── .env.example                       # Template de variáveis de ambiente
├── docker-compose.yml                 # PostgreSQL + n8n (opcional)
│
├── config/
│   ├── database.py                    # Configurações do PostgreSQL
│   ├── gmail_config.py                # Credenciais Gmail API
│   └── whatsapp_config.py             # Configurações WhatsApp API
│
├── src/
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py          # Lógica de extração (SafetyDoc AI base)
│   │   ├── validators.py             # Validações de dados extraídos
│   │   └── duplicate_checker.py      # Detector de PCMSOs duplicados
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py                 # SQLAlchemy models (Empresas, Colaboradores, Exames)
│   │   ├── migrations/               # Alembic migrations
│   │   └── queries.py                # Queries reutilizáveis
│   │
│   ├── business_logic/
│   │   ├── __init__.py
│   │   ├── alert_engine.py           # Motor de regras (10-15 dias)
│   │   ├── message_generator.py      # Templates de mensagens
│   │   └── report_builder.py         # Relatórios mensais
│   │
│   ├── communications/
│   │   ├── __init__.py
│   │   ├── gmail_sender.py           # Envio via Gmail
│   │   └── whatsapp_sender.py        # Envio via WhatsApp
│   │
│   ├── validation_interface/
│   │   ├── __init__.py
│   │   ├── web_validator.py          # Interface web para técnico validar
│   │   └── templates/                # HTML templates (Flask/FastAPI)
│   │
│   └── dashboard/
│       ├── __init__.py
│       ├── app.py                    # Dashboard web (Streamlit ou Dash)
│       └── components/               # Componentes do dashboard
│
├── n8n_workflows/
│   ├── workflow_daily_alerts.json    # Workflow n8n para alertas diários
│   ├── workflow_upload_pcmso.json    # Workflow para ingestão de PCMSO
│   └── workflow_monthly_report.json  # Workflow relatório mensal
│
├── scripts/
│   ├── init_database.py              # Criar schema inicial
│   ├── seed_test_data.py             # Dados de teste
│   └── run_extraction.py             # Script manual de extração
│
├── tests/
│   ├── test_extraction.py
│   ├── test_alerts.py
│   └── test_communications.py
│
└── data/
    ├── pcmso_raw/                    # PDFs originais
    ├── pcmso_pending_validation/     # Dados aguardando validação
    └── pcmso_processed/              # PDFs já processados
```

## MODELO DE DADOS POSTGRESQL

### Tabelas Principais:

```sql
-- Empresas Clientes
CREATE TABLE empresas (
    id SERIAL PRIMARY KEY,
    razao_social VARCHAR(255) NOT NULL,
    nome_fantasia VARCHAR(255),
    cnpj VARCHAR(18) UNIQUE NOT NULL,
    email_sso VARCHAR(255) NOT NULL,        -- Email do departamento SSO
    telefone_sso VARCHAR(20),
    whatsapp_sso VARCHAR(20),
    data_cadastro TIMESTAMP DEFAULT NOW(),
    ativo BOOLEAN DEFAULT TRUE
);

-- Colaboradores
CREATE TABLE colaboradores (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id),
    nome_completo VARCHAR(255) NOT NULL,
    cpf VARCHAR(14) UNIQUE NOT NULL,
    cargo VARCHAR(100),
    setor VARCHAR(100),
    data_admissao DATE,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tipos de Exames
CREATE TABLE tipos_exames (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL,
    descricao TEXT,
    periodicidade_meses INTEGER NOT NULL,    -- Ex: 12 meses (anual)
    criticidade VARCHAR(20) DEFAULT 'normal' -- alta, normal, baixa
);

-- Exames Realizados/Agendados
CREATE TABLE exames (
    id SERIAL PRIMARY KEY,
    colaborador_id INTEGER REFERENCES colaboradores(id),
    tipo_exame_id INTEGER REFERENCES tipos_exames(id),
    data_ultimo_exame DATE,
    data_proximo_exame DATE NOT NULL,        -- Calculado automaticamente
    status VARCHAR(20) DEFAULT 'pendente',   -- pendente, agendado, realizado, vencido
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Histórico de Alertas Enviados
CREATE TABLE alertas_enviados (
    id SERIAL PRIMARY KEY,
    exame_id INTEGER REFERENCES exames(id),
    empresa_id INTEGER REFERENCES empresas(id),
    canal VARCHAR(20) NOT NULL,              -- email, whatsapp
    mensagem TEXT,
    status_envio VARCHAR(20),                -- enviado, falhou, pendente
    data_envio TIMESTAMP DEFAULT NOW()
);

-- Fila de Validação Técnica
CREATE TABLE validacao_pendente (
    id SERIAL PRIMARY KEY,
    pcmso_filename VARCHAR(255) NOT NULL,
    empresa_id INTEGER REFERENCES empresas(id),
    dados_extraidos JSONB,                   -- JSON com dados extraídos do PDF
    status VARCHAR(20) DEFAULT 'pendente',   -- pendente, aprovado, rejeitado
    observacoes_tecnico TEXT,
    validado_por VARCHAR(100),
    data_upload TIMESTAMP DEFAULT NOW(),
    data_validacao TIMESTAMP
);

-- Versões de PCMSO (controle de versionamento)
CREATE TABLE pcmso_versoes (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER REFERENCES empresas(id),
    versao INTEGER NOT NULL,
    ano_referencia INTEGER NOT NULL,
    arquivo_path VARCHAR(500),
    hash_arquivo VARCHAR(64) UNIQUE,         -- MD5/SHA256 para detectar duplicatas
    data_upload TIMESTAMP DEFAULT NOW(),
    UNIQUE(empresa_id, ano_referencia, versao)
);

-- Índices para performance
CREATE INDEX idx_exames_data_proximo ON exames(data_proximo_exame);
CREATE INDEX idx_colaboradores_empresa ON colaboradores(empresa_id);
CREATE INDEX idx_alertas_data ON alertas_enviados(data_envio);
```

## FUNCIONALIDADES DETALHADAS

### 1. MÓDULO DE EXTRAÇÃO (src/extraction/)

**pdf_extractor.py**:
- Reutilizar lógica do SafetyDoc AI
- Extrair:
  - Dados da empresa (CNPJ, razão social)
  - Lista de colaboradores (nome, CPF, cargo, setor)
  - Exames por colaborador (tipo, periodicidade, última realização)
- Gerar JSON estruturado com dados extraídos
- Calcular hash MD5 do PDF para detecção de duplicatas

**duplicate_checker.py**:
- Verificar hash do arquivo contra `pcmso_versoes`
- Se duplicado EXATO: retornar erro ao técnico
- Se mesma empresa + ano diferente: sinalizar como nova versão
- Sugerir ações (substituir, manter ambas, rejeitar)

**validators.py**:
- Validações básicas:
  - CNPJ válido (formato e dígitos verificadores)
  - CPF válido
  - Datas coerentes (data_ultimo_exame < data_proximo_exame)
  - Periodicidade dentro de padrões (6, 12, 24, 36 meses)

### 2. INTERFACE DE VALIDAÇÃO TÉCNICA (src/validation_interface/)

**Requisitos**:
- Interface web simples (Flask ou FastAPI + HTML/CSS)
- Dashboard mostrando:
  - Lista de PCMSOs pendentes de validação
  - Dados extraídos lado a lado com preview do PDF
  - Campos editáveis para correção
  - Botões: ✅ Aprovar | ❌ Rejeitar | ✏️ Editar e Aprovar
- Após aprovação: inserir dados no PostgreSQL e mover para `pcmso_processed/`

**Tela de validação deve mostrar**:
```
┌────────────────────────────────────────────────────┐
│ PCMSO Pendente de Validação                        │
├────────────────────────────────────────────────────┤
│ Arquivo: PCMSO_EmpresaXYZ_2025.pdf                 │
│ Data Upload: 07/04/2026 14:30                      │
│ Status Duplicata: ⚠️ Nova versão (ano 2025)        │
├────────────────────────────────────────────────────┤
│ EMPRESA                                            │
│ CNPJ: 12.345.678/0001-90  ✓                        │
│ Razão Social: Empresa XYZ Ltda  ✓                  │
│ Email SSO: sso@empresaxyz.com.br  ✓                │
├────────────────────────────────────────────────────┤
│ COLABORADORES ENCONTRADOS: 45                      │
│ ┌──────────────────────────────────────────┐       │
│ │ Nome          │ CPF         │ Cargo      │       │
│ │ João Silva    │ 123.456.789 │ Operador   │ ✓     │
│ │ Maria Santos  │ 987.654.321 │ Analista   │ ⚠️    │  ← CPF inválido
│ └──────────────────────────────────────────┘       │
├────────────────────────────────────────────────────┤
│ EXAMES EXTRAÍDOS: 180                              │
│ [Tabela editável com validações inline]            │
├────────────────────────────────────────────────────┤
│ [Aprovar]  [Editar]  [Rejeitar]                    │
└────────────────────────────────────────────────────┘
```

### 3. MOTOR DE ALERTAS (src/business_logic/alert_engine.py)

**Lógica de Execução Diária**:
```python
def processar_alertas_diarios():
    """
    Executado todo dia às 05:00 AM via n8n
    """
    hoje = date.today()
    janela_inicio = hoje + timedelta(days=10)
    janela_fim = hoje + timedelta(days=15)
    
    # Buscar exames vencendo entre 10-15 dias
    exames_proximos = query_exames_por_vencimento(janela_inicio, janela_fim)
    
    # Agrupar por empresa
    alertas_por_empresa = agrupar_por_empresa(exames_proximos)
    
    # Para cada empresa, gerar mensagem personalizada
    for empresa_id, lista_exames in alertas_por_empresa.items():
        empresa = get_empresa(empresa_id)
        
        # Gerar mensagem
        mensagem_email = gerar_email_alerta(empresa, lista_exames)
        mensagem_whatsapp = gerar_whatsapp_alerta(empresa, lista_exames)
        
        # Enviar
        enviar_email(empresa.email_sso, mensagem_email)
        enviar_whatsapp(empresa.whatsapp_sso, mensagem_whatsapp)
        
        # Registrar no histórico
        registrar_alerta(empresa_id, lista_exames, 'email')
        registrar_alerta(empresa_id, lista_exames, 'whatsapp')
```

**Template de E-mail**:
```
Assunto: ⚠️ [Empresa XYZ] - 12 exames ocupacionais vencendo em 10-15 dias

Prezado Departamento de SSO,

Identificamos que 12 colaboradores da sua empresa possuem exames ocupacionais 
com vencimento próximo (entre 10 e 15 dias):

┌─────────────────────────────────────────────────────────────┐
│ Colaborador          │ Exame              │ Vencimento      │
├─────────────────────────────────────────────────────────────┤
│ João Silva           │ Audiometria        │ 20/04/2026      │
│ Maria Santos         │ Hemograma Completo │ 22/04/2026      │
│ ...                                                          │
└─────────────────────────────────────────────────────────────┘

📊 Acesse o dashboard da sua empresa para mais detalhes:
https://sistema.com.br/empresa/12345

Atenciosamente,
Sistema PCMSO Alert
```

**Template WhatsApp**:
```
🚨 *Alerta PCMSO - Empresa XYZ*

12 exames vencendo nos próximos 10-15 dias:

• João Silva - Audiometria (20/04)
• Maria Santos - Hemograma (22/04)
...

📊 Detalhes: https://sistema.com.br/empresa/12345
```

### 4. WORKFLOWS N8N

**workflow_daily_alerts.json**:
```
[Cron: 05:00 AM] 
  → [HTTP Request: localhost:5000/api/processar-alertas]
  → [Function: Processar Resposta]
  → [Conditional: Se houver alertas]
       → [Gmail: Enviar Emails em lote]
       → [WhatsApp: Enviar mensagens]
  → [Webhook: Notificar conclusão]
```

**workflow_upload_pcmso.json**:
```
[Watch Folder: data/pcmso_raw/]
  → [HTTP Request: localhost:5000/api/extrair-pcmso]
  → [Function: Validar Duplicata]
  → [Conditional: Se duplicado]
       → [Email: Notificar técnico]
  → [Conditional: Se novo]
       → [Database: Inserir em validacao_pendente]
       → [Slack/Email: Notificar técnico para validação]
```

**workflow_monthly_report.json**:
```
[Cron: Dia 1 de cada mês às 08:00]
  → [HTTP Request: /api/relatorio-mensal]
  → [Function: Gerar PDF]
  → [Gmail: Enviar para todas empresas]
  → [Database: Registrar envio]
```

### 5. DASHBOARD WEB (src/dashboard/)

**Tecnologia sugerida**: Streamlit ou Dash (Python-based)

**Páginas**:

1. **Login por Empresa** (autenticação simples por CNPJ + senha)

2. **Visão Geral**:
   - Total de colaboradores ativos
   - Total de exames em dia / vencidos / próximos
   - Gráfico de vencimentos nos próximos 90 dias
   - Últimos alertas recebidos

3. **Colaboradores**:
   - Tabela filtável/ordenável
   - Status de exames por colaborador
   - Ações: Ver histórico, baixar relatório individual

4. **Exames**:
   - Calendário de vencimentos
   - Lista de exames pendentes/agendados/realizados
   - Filtros: por tipo, por período, por status

5. **Relatórios**:
   - Relatório mensal em PDF
   - Exportar dados para Excel
   - Histórico de comunicações recebidas

6. **(FUTURO) Integração eSocial**:
   - Status de conformidade
   - Eventos S-2220 enviados
   - Pendências fiscais

## REQUISITOS TÉCNICOS

### requirements.txt

```txt
# Core
python-dotenv==1.0.0
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23
alembic==1.13.1

# Extração PDF (SafetyDoc AI base)
pdfplumber==0.10.3
tabula-py==2.9.0
PyPDF2==3.0.1
pandas==2.1.4

# API/Web
fastapi==0.108.0
uvicorn==0.25.0
streamlit==1.29.0
jinja2==3.1.2

# Comunicação
google-api-python-client==2.110.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
twilio==8.11.1
requests==2.31.0

# Utilities
python-dateutil==2.8.2
schedule==1.2.0
```

### Variáveis de Ambiente (.env)

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pcmso_alerts
DB_ECHO=False

# Gmail API
GMAIL_CREDENTIALS_FILE=config/gmail_credentials.json
GMAIL_TOKEN_FILE=config/gmail_token.json
GMAIL_SENDER_EMAIL=alertas@seudominio.com.br

# WhatsApp (Twilio ou Evolution API)
WHATSAPP_API_KEY=your_api_key
WHATSAPP_PHONE_NUMBER=+5598912345678

# n8n
N8N_WEBHOOK_URL=http://localhost:5678/webhook/
N8N_API_KEY=your_n8n_api_key

# App
SECRET_KEY=your_secret_key_here
ENVIRONMENT=development
LOG_LEVEL=INFO

# Paths
PCMSO_RAW_PATH=data/pcmso_raw/
PCMSO_PENDING_PATH=data/pcmso_pending_validation/
PCMSO_PROCESSED_PATH=data/pcmso_processed/
```

## CRITÉRIOS DE SUCESSO (MVP)

✅ **Fase 1 Completa**:
- Upload de PCMSO → Extração → Fila de Validação → Banco PostgreSQL
- Detecção de duplicatas funcional
- Interface web de validação operacional

✅ **Fase 2 Completa**:
- Motor de alertas funcionando diariamente
- Cálculo correto de vencimentos (10-15 dias)
- Registro de histórico de alertas

✅ **Fase 3 Completa**:
- Envio automático via Gmail ✅
- Envio automático via WhatsApp ✅
- Relatório mensal consolidado por empresa

✅ **Fase 4 Completa**:
- Dashboard web acessível por empresa
- Visualização de exames, colaboradores e alertas
- Exportação de relatórios em PDF/Excel

## PRÓXIMOS PASSOS (PÓS-MVP)

- [ ] Integração com APIs de clínicas para agendamento automático
- [ ] Integração com eSocial (eventos S-2220)
- [ ] Sistema de notificações push (web push notifications)
- [ ] App mobile para técnicos (validação via celular)
- [ ] IA para classificação automática de exames (reduzir validação manual)
- [ ] Multi-tenancy (SaaS para múltiplas empresas de SSO)

## INSTRUÇÕES FINAIS PARA CLAUDE CODE

1. **Gere TODO o código necessário** para o MVP funcional
2. **Priorize clareza e documentação**: cada módulo deve ter docstrings detalhadas
3. **Crie scripts de setup**: `init_database.py`, `seed_test_data.py`
4. **Inclua testes unitários básicos** para extração e alertas
5. **Documente o passo a passo** no README.md para:
   - Configurar PostgreSQL local
   - Instalar dependências
   - Configurar Gmail API
   - Executar primeira extração
   - Iniciar n8n e importar workflows
   - Rodar dashboard
6. **Use type hints** em todas as funções Python
7. **Siga PEP 8** para formatação
8. **Crie logs detalhados** em cada etapa crítica

## EXEMPLO DE FLUXO COMPLETO (USER STORY)

```
1. Técnico recebe PCMSO_EmpresaABC_2026.pdf por email
2. Salva em data/pcmso_raw/
3. n8n detecta novo arquivo → trigger workflow_upload_pcmso
4. Python extrai dados → gera JSON → verifica duplicatas
5. Sistema insere em `validacao_pendente` com status='pendente'
6. Técnico recebe email: "Novo PCMSO aguardando validação"
7. Técnico acessa http://localhost:5000/validacao
8. Revisa dados extraídos, corrige 2 CPFs inválidos
9. Clica em "Aprovar"
10. Sistema insere 45 colaboradores + 180 exames no PostgreSQL
11. Move PDF para data/pcmso_processed/
12. Sistema calcula data_proximo_exame para cada registro
13. Todo dia às 05:00, n8n executa workflow_daily_alerts
14. Motor de alertas identifica 12 exames vencendo em 10-15 dias
15. Gera email + WhatsApp personalizados
16. Envia para sso@empresaabc.com.br
17. Empresa acessa dashboard → vê lista de exames pendentes
18. Agenda exames para colaboradores
19. Fim do mês: relatório consolidado enviado automaticamente
```

---

**COMECE AGORA! Gere o código completo para este MVP.**
