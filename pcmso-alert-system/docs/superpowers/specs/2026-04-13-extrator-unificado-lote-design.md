# Design: Extrator Unificado em Lote — PCMSO Alert System

**Data:** 2026-04-13  
**Escopo:** Etapa de extração — unificação do extrator legado com o alert system, processamento em lote via n8n, saída em Excel para revisão técnica, conversão para JSON e inserção em fila de validação.

---

## 1. Contexto

O projeto possui dois extratores independentes:

- **Legado** (`PCMSO/pcmso_extractor.py`): processa lotes de PDFs, extrai empresa/cargos/riscos/exames via regex, gera Excel consolidado.
- **Alert System** (`src/extraction/pdf_extractor.py`): processa um PDF por vez, extrai empresa/colaboradores/cargo_exames via tabelas pdfplumber, grava em `ValidacaoPendente`.

O objetivo é unificar em um único extrator que cubra os dois domínios, integrado ao n8n, com saída em Excel para revisão pelo técnico de segurança antes da entrada no banco.

---

## 2. Fluxo Completo

```
n8n Workflow 1 — Extração
  POST /extrair-lote  (N PDFs como multipart/form-data)
        │
        ▼
  Extrator Unificado (Python/FastAPI)
  └── Por PDF: regex (empresa, cargos, riscos, vigência, médico, email, whatsapp)
             + tabelas pdfplumber (colaboradores, cargo×exame, exames com datas)
        │
        ▼
  PCMSO_Lote_YYYY-MM-DD.xlsx  ← retornado ao n8n como arquivo binário
        │
        ▼
  n8n entrega Excel ao técnico (email ou pasta compartilhada)

────────────────────────────────────────────────────────

Técnico revisa e edita o Excel (6 abas)

────────────────────────────────────────────────────────

n8n Workflow 2 — Conversão e Fila
  Técnico faz upload do Excel editado no n8n
        │
        ▼
  POST /converter-excel  (arquivo .xlsx)
        │
        ▼
  Um registro por empresa em ValidacaoPendente (dados_extraidos JSONB)
        │
        ▼
  Interface web (web_validator.py) — técnico aprova/rejeita
        │
        ▼
  Efetivação no PostgreSQL  ← fora do escopo desta etapa
```

---

## 3. Estrutura do Excel de Saída

Seis abas, uma por domínio:

| Aba | Colunas principais |
|---|---|
| **Empresas** | arquivo, razao_social, cnpj, nome_fantasia, grau_risco, cnae, endereco, num_profissionais, medico_pcmso, responsavel_empresa, vigencia_inicio, vigencia_fim, email_sso, whatsapp_sso |
| **Cargos** | arquivo, razao_social, setor, cargo, quantidade |
| **Riscos** | arquivo, razao_social, tipo_risco, descricao_risco, danos_saude |
| **Exames** | arquivo, razao_social, exame, periodicidade |
| **Colaboradores** | arquivo, razao_social, nome_completo, cpf, cargo, setor, data_admissao |
| **Cargo_Exames** | arquivo, razao_social, cargo, setor, risco, tipo_exame, periodicidade_meses |

- Campo `arquivo` em todas as abas permite rastrear qual PDF originou cada linha.
- Campos não encontrados recebem string vazia (não "N/A") para facilitar edição.
- Erros de extração por arquivo vão para uma aba extra **Erros** (opcional, sempre gerada).

---

## 4. Estrutura JSON para ValidacaoPendente

Após conversão do Excel editado, cada empresa gera um registro:

```json
{
  "arquivo": "PCMSO_EmpresaX_2025.pdf",
  "hash": "abc123...",
  "empresa": {
    "razao_social": "Empresa X Ltda",
    "cnpj": "12.345.678/0001-99",
    "nome_fantasia": "",
    "grau_risco": "2 (Médio)",
    "cnae": "45.11-1-01",
    "endereco": "Rua das Flores, 100",
    "num_profissionais": "42",
    "medico_pcmso": "Dr. João Silva",
    "responsavel_empresa": "Maria Souza",
    "vigencia_inicio": "01/01/2025",
    "vigencia_fim": "31/12/2025",
    "email_sso": "sso@empresax.com.br",
    "whatsapp_sso": "(98) 99999-0000"
  },
  "cargos": [
    { "setor": "EST ADMINISTRATIVO", "cargo": "AUXILIAR ADMINISTRATIVO", "quantidade": "3" }
  ],
  "riscos": [
    { "tipo": "ERGONÔMICO", "risco": "Movimentos repetitivos", "danos": "LER/DORT" }
  ],
  "exames": [
    { "exame": "Audiometria", "periodicidade": "Anual" }
  ],
  "colaboradores": [
    { "nome_completo": "José Silva", "cpf": "12345678900", "cargo": "Motorista", "setor": "Logística", "data_admissao": "2022-03-15" }
  ],
  "cargo_exames": [
    { "cargo": "Motorista", "setor": "Logística", "risco": "MECÂNICO", "tipo_exame": "Acuidade Visual", "periodicidade_meses": 12 }
  ],
  "erros_extracao": []
}
```

---

## 5. Componentes Novos e Alterados

| Arquivo | Tipo | O que faz |
|---|---|---|
| `src/extraction/pdf_extractor.py` | **Alterado** | Absorve lógica do legado: cargos/riscos via regex, vigência, médico PCMSO, email/whatsapp. Mantém extração por tabelas. |
| `src/extraction/excel_builder.py` | **Novo** | Recebe lista de resultados de extração e gera `.xlsx` com 6 abas + aba Erros. |
| `src/extraction/excel_converter.py` | **Novo** | Lê Excel editado pelo técnico e converte para lista de dicts no formato JSON acima. |
| `src/api/routes/extracao.py` | **Novo** | `POST /extrair-lote` — recebe N PDFs, processa em paralelo, retorna Excel. |
| `src/api/routes/conversao.py` | **Novo** | `POST /converter-excel` — recebe Excel editado, insere em `ValidacaoPendente`. |
| `src/api/main.py` | **Novo** | App FastAPI mínimo, registra routers. |
| `scripts/run_extraction.py` | **Alterado** | Atualizado para usar extrator unificado. |

**Não alterados:** `models.py`, `web_validator.py`, motor de alertas, workflows n8n existentes.

---

## 6. Decisões Técnicas

- **Paralelismo:** `ThreadPoolExecutor` no endpoint `/extrair-lote` — um thread por PDF.
- **Extração híbrida:** regex para campos de texto livre (empresa, cargos, riscos), pdfplumber para tabelas estruturadas (colaboradores, exames com datas).
- **Filtro de cabeçalho:** mantém o filtro Prevenclínica do legado (`_filter_provider_header`).
- **Deduplicação:** cargos e riscos deduplicados por chave composta antes de entrar no Excel.
- **Erros não fatais:** arquivos com erro parcial entram no Excel com dados disponíveis + linha na aba Erros.

---

## 7. Fora do Escopo

- Efetivação dos dados aprovados no PostgreSQL (próxima etapa).
- Alterações na interface de validação (`web_validator.py`).
- Workflows n8n (configuração pelo usuário após a API estar pronta).
