# 🚀 Guia de Próximos Passos - SafetyDoc AI
## Desafio Fase 1 - Rocketseat

---

## ✅ O que já foi criado:

1. **Documento do Produto** (`SafetyDoc_AI_Documento_Produto.md`)
   - 18KB de conteúdo completo
   - Inclui: Problema, Solução, Público-alvo, Funcionalidades, Casos de Uso, Roadmap
   
2. **Prompt do Assistente** (`SafetyDoc_AI_Prompt_Assistente.md`)
   - 15KB com prompt completo
   - Técnicas: Role-Playing + Few-Shot Learning
   - 8 exemplos práticos de interação

---

## 📋 Checklist para Completar o Desafio

### Passo 1: Converter Documentos para PDF

Como o ambiente teve problemas de rede, você precisará converter os arquivos Markdown para PDF localmente.

**Opção A - Online (mais fácil):**
1. Acesse: https://www.markdowntopdf.com/
2. Faça upload de cada arquivo .md
3. Download do PDF gerado

**Opção B - Local (se tiver Python):**
```bash
pip install markdown weasyprint
python -c "
import markdown
from weasyprint import HTML
from pathlib import Path

for md_file in ['SafetyDoc_AI_Documento_Produto.md', 'SafetyDoc_AI_Prompt_Assistente.md']:
    with open(md_file, 'r', encoding='utf-8') as f:
        html = markdown.markdown(f.read(), extensions=['tables', 'fenced_code'])
    HTML(string=f'<html><body>{html}</body></html>').write_pdf(md_file.replace('.md', '.pdf'))
"
```

**Opção C - Google Docs:**
1. Abra Google Docs
2. Arquivo → Importar → Copie e cole o conteúdo do .md
3. Arquivo → Download → PDF

---

### Passo 2: Gerar Planilha Excel com Dados Estruturados

Você tem duas opções:

**Opção A - Rodar o Extrator (RECOMENDADO):**

1. Certifique-se de ter os PDFs de PCMSO em uma pasta
2. Coloque o arquivo `pcmso_extractor.py` na mesma pasta
3. Execute:
```bash
python pcmso_extractor.py
```
4. Isso gerará: `PCMSO_Consolidado.xlsx` com 4 abas

**Opção B - Criar Planilha Manualmente (se o extrator falhar):**

Crie um arquivo Excel com 4 abas seguindo esta estrutura:

**Aba "Empresa":**
| id_empresa | razao_social | cnpj | cnae | grau_risco | endereco | num_profissionais | medico_pcmso | vigencia_inicio | vigencia_fim |
|------------|--------------|------|------|------------|----------|-------------------|--------------|-----------------|--------------|
| 1 | EXEMPLO LTDA | 12.345.678/0001-90 | 47.73-3-00 | 3 (Médio) | Av. Exemplo, 123 | 25 | Dr. João Silva - CRM 12345 | 01/01/2025 | 31/12/2025 |

**Aba "Cargos":**
| id_empresa | razao_social | setor | cargo | quantidade |
|------------|--------------|-------|-------|------------|
| 1 | EXEMPLO LTDA | ADMINISTRATIVO | AUXILIAR ADMINISTRATIVO | 3 |
| 1 | EXEMPLO LTDA | OPERACIONAL | MOTORISTA | 5 |

**Aba "Riscos":**
| id_empresa | razao_social | tipo_risco | descricao_risco | danos_saude |
|------------|--------------|------------|-----------------|-------------|
| 1 | EXEMPLO LTDA | ERGONÔMICO | Postura inadequada | LER/DORT |
| 1 | EXEMPLO LTDA | MECÂNICO | Acidentes de trânsito | Lesões traumáticas |

**Aba "Exames":**
| id_empresa | razao_social | exame | periodicidade |
|------------|--------------|-------|---------------|
| 1 | EXEMPLO LTDA | Exame Clínico Ocupacional | Anual |
| 1 | EXEMPLO LTDA | Acuidade Visual | Anual |
| 1 | EXEMPLO LTDA | Audiometria | Anual |

⚠️ **Importante:** Use dados de pelo menos 1 empresa real (se possível, rode o extrator nos PDFs que você tem).

---

### Passo 3: Configurar o Google NotebookLM

1. **Acesse:** https://notebooklm.google.com/
2. **Crie novo notebook:** "SafetyDoc AI - Assistente PCMSO"
3. **Faça upload dos 3 arquivos:**
   - ✅ `SafetyDoc_AI_Documento_Produto.pdf`
   - ✅ `SafetyDoc_AI_Prompt_Assistente.pdf` (ou use apenas o texto do prompt)
   - ✅ `PCMSO_Consolidado.xlsx`

4. **Configure o comportamento:**
   - Clique em "Configurações" ou "Personalizar"
   - Na seção "Instruções personalizadas" ou "System Prompt"
   - **Copie e cole todo o conteúdo da seção "PROMPT COMPLETO"** do arquivo `SafetyDoc_AI_Prompt_Assistente.md`
     - (É o bloco que começa com: "# IDENTIDADE E PAPEL" e termina antes de "Notas de Implementação")

---

### Passo 4: Testar o Assistente

Faça perguntas de teste para validar o comportamento:

1. **Teste básico:**
   - "Quais são os riscos do cargo de motorista?"

2. **Teste de exames:**
   - "Quais exames são obrigatórios para auxiliar administrativo?"

3. **Teste de dados da empresa:**
   - "Qual o CNPJ da empresa e quando vence o PCMSO?"

4. **Teste de limitação:**
   - "Me ajude a calcular o dimensionamento do SESMT"
   - (Deve recusar educadamente)

5. **Teste de rastreabilidade:**
   - Verifique se todas as respostas citam a fonte (aba do Excel)

---

### Passo 5: Tornar Público e Compartilhar

**Importante para o desafio:**

1. **No NotebookLM:**
   - Clique no botão "Compartilhar" (canto superior direito)
   - Em "Acesso ao notebook" → Selecione "qualquer pessoa com o link"
   - **Marque a opção "Todo o notebook"** (para que os arquivos fiquem visíveis)
   - Clique em "Salvar"

2. **Copie o link público** (formato: https://notebooklm.google.com/notebook/...)

3. **Teste o link:**
   - Abra em uma aba anônima
   - Verifique se consegue ver:
     - Os 3 arquivos carregados
     - Consegue fazer perguntas ao assistente

---

### Passo 6: Submeter o Desafio

No portal da Rocketseat:
1. Cole o **link público** do seu NotebookLM
2. Certifique-se de que:
   - ✅ O assistente está público e acessível
   - ✅ Os arquivos (Documento do Produto, Prompt, Excel) estão visíveis
   - ✅ O comportamento atende aos requisitos:
     - Mínimo 2 técnicas de prompt (Role-Playing ✅ + Few-Shot ✅)
     - Assistente se comporta como especialista
     - Respostas são precisas e rastreáveis

---

## 🎯 Critérios de Avaliação (lembre-se)

O avaliador vai verificar:

1. **Documento do Produto:**
   - ✅ Descrição clara do problema e solução
   - ✅ Público-alvo bem definido
   - ✅ Escopo e limitações explícitas

2. **Prompt do Assistente:**
   - ✅ Uso de 2+ técnicas de engenharia de prompt
   - ✅ Personalidade e comportamento bem definidos
   - ✅ Exemplos práticos (Few-Shot)

3. **Comportamento do Assistente:**
   - ✅ Não especula nem inventa informações
   - ✅ Cita fontes corretamente
   - ✅ Tom técnico-acessível
   - ✅ Reconhece limitações explicitamente

---

## 💡 Dicas Finais

### Para destacar seu projeto:

1. **Teste extensivamente** antes de submeter
2. **Se possível, use dados reais** (rodando o extrator)
3. **Documente edge cases** (como o assistente lida com perguntas fora do escopo)
4. **Considere postar no LinkedIn:**
   - Mostre o processo de criação
   - Compartilhe aprendizados sobre prompt engineering
   - Marque @Rocketseat

### Se tiver problemas:

**Problema:** Extrator não roda ou dá erro
**Solução:** Crie planilha Excel manualmente com dados fictícios, mas realistas

**Problema:** NotebookLM não aceita Excel
**Solução:** Converta Excel para CSV ou crie um PDF com tabelas

**Problema:** Assistente não respeita o prompt
**Solução:** Refine as instruções, adicione mais exemplos (Few-Shot)

---

## 📊 Estrutura Final dos Arquivos

```
NotebookLM/
├── 📄 SafetyDoc_AI_Documento_Produto.pdf (Base de conhecimento sobre o produto)
├── 📄 SafetyDoc_AI_Prompt_Assistente.pdf (Opcional, pode colar direto nas configurações)
└── 📊 PCMSO_Consolidado.xlsx (Dados estruturados - 4 abas)
    ├── Aba 1: Empresa
    ├── Aba 2: Cargos
    ├── Aba 3: Riscos
    └── Aba 4: Exames
```

---

## 🎓 Conceitos Aplicados

### Técnicas de Prompt Engineering Utilizadas:

1. **Role-Playing (Personificação do Especialista):**
   ```
   "Você é o SafetyDoc AI, um assistente especializado em saúde e 
   segurança do trabalho no Brasil..."
   ```
   - Define identidade clara
   - Estabelece expertise e limitações
   - Cria personalidade consistente

2. **Few-Shot Learning (Aprendizado por Exemplos):**
   ```
   ## Exemplo 1: Consulta de Riscos
   Usuário: "Quais são os riscos do cargo de motorista?"
   SafetyDoc AI: [resposta completa formatada]
   ```
   - 8 exemplos práticos
   - Cobrem diferentes tipos de consulta
   - Demonstram formato esperado de resposta

3. **Chain of Thought (Raciocínio Passo a Passo):**
   ```
   1. Identificar a intenção
   2. Localizar na base
   3. Verificar disponibilidade
   4. Estruturar resposta
   5. Validar precisão
   ```
   - Processo mental explícito
   - Garante consistência

4. **Structured Output (Saída Estruturada):**
   - Templates de resposta por tipo de consulta
   - Formato consistente com citação de fonte
   - Organização clara da informação

---

## 📞 Suporte

Se tiver dúvidas durante a implementação, você pode:
- Revisar este guia
- Consultar a documentação do NotebookLM
- Revisar o ebook de Prompt Engineering da Rocketseat

---

**Boa sorte no desafio! 🚀**

*SafetyDoc AI - Transformando dados ocupacionais em conhecimento acessível*