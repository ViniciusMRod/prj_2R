# SafetyDoc AI
## Inteligência em Saúde do Trabalho

---

## Índice

1. [Introdução](#introdução)
2. [O Problema](#o-problema)
3. [A Solução](#a-solução)
4. [Público-Alvo](#público-alvo)
5. [Funcionalidades do MVP](#funcionalidades-do-mvp)
6. [Casos de Uso Práticos](#casos-de-uso-práticos)
7. [Estrutura de Dados](#estrutura-de-dados)
8. [Diferenciais Competitivos](#diferenciais-competitivos)
9. [Limitações e Escopo](#limitações-e-escopo)
10. [Roadmap Futuro](#roadmap-futuro)

---

## Introdução

### Contexto da Saúde Ocupacional no Brasil

A saúde e segurança do trabalho no Brasil é regulamentada por uma série de Normas Regulamentadoras (NRs) que exigem das empresas a elaboração e manutenção de diversos documentos técnicos. Entre eles, destaca-se o **PCMSO (Programa de Controle Médico de Saúde Ocupacional)**, documento obrigatório para todas as empresas que possuem empregados regidos pela CLT.

O PCMSO é um documento extenso e técnico que contém informações críticas sobre:
- Riscos ocupacionais por cargo/função
- Exames médicos obrigatórios
- Periodicidade de avaliações de saúde
- Medidas preventivas e recomendações

### O Desafio Atual

Gestores de Saúde e Segurança do Trabalho, profissionais de RH, médicos do trabalho e engenheiros de segurança enfrentam diariamente o desafio de consultar esses documentos para responder perguntas operacionais críticas. A dificuldade de navegação e a falta de padronização desses documentos resultam em:

- **Perda de tempo** procurando informações específicas
- **Risco de não conformidade** por desconhecimento de requisitos
- **Retrabalho** por consultas repetitivas
- **Dificuldade de integração** com sistemas de gestão

**SafetyDoc AI** foi criado para resolver esse problema.

---

## O Problema

### Dores Identificadas

#### 1. Documentos Longos e Pouco Padronizados
Os PCMSOs podem ter dezenas de páginas com estruturas variadas entre diferentes empresas e prestadores de serviço. Não há um formato único, o que dificulta a localização rápida de informações.

#### 2. Consultas Recorrentes e Repetitivas
Profissionais precisam responder frequentemente às mesmas perguntas:
- "Qual exame é obrigatório para o cargo X?"
- "Quais riscos estão associados ao cargo Y?"
- "Qual a periodicidade do exame Z?"
- "Existe alguma recomendação especial para gestantes?"

#### 3. Dificuldade de Rastreabilidade
Quando uma informação é encontrada, muitas vezes não há referência clara de onde ela veio no documento original, dificultando auditorias e validações.

#### 4. Conhecimento Técnico Necessário
A linguagem técnica dos documentos exige conhecimento especializado, criando barreiras para profissionais de outras áreas que precisam consultar informações pontuais.

#### 5. Múltiplos Documentos por Empresa
Empresas com várias unidades ou CNPJs possuem múltiplos PCMSOs, tornando a gestão ainda mais complexa.

---

## A Solução

### SafetyDoc AI - Visão Geral

**SafetyDoc AI** é um assistente inteligente especializado em documentos de saúde ocupacional que permite consultas rápidas, precisas e rastreáveis sobre informações contidas em PCMSOs estruturados.

### Como Funciona

O SafetyDoc AI opera em duas camadas:

#### Camada 1: Base de Dados Estruturada
Os dados dos PCMSOs são previamente organizados em uma estrutura relacional com 4 componentes principais:

1. **Empresa** - Dados cadastrais, grau de risco, vigência do programa
2. **Cargos** - Funções, setores e quantidade de colaboradores
3. **Riscos** - Tipos de risco, descrições e danos à saúde
4. **Exames** - Tipos de exames e periodicidade

#### Camada 2: Assistente Conversacional
O usuário faz perguntas em **linguagem natural** e o assistente:
- Localiza a informação na base estruturada
- Retorna resposta objetiva e didática
- Cita a fonte/seção do documento original
- Esclarece dúvidas com exemplos práticos

### Exemplo de Interação

**Usuário:** "Quais exames ocupacionais são obrigatórios para o cargo de motorista?"

**SafetyDoc AI:** "Para o cargo de **MOTORISTA**, os seguintes exames ocupacionais são obrigatórios:

- **Exame Clínico Ocupacional** - Anual
- **Acuidade Visual** - Anual
- **Audiometria** - Anual (devido à exposição a ruído)
- **Avaliação Psicológica** - A cada 2 anos (conforme Resolução CONTRAN)

**Fonte:** Tabela de Exames por Cargo, Seção 4.3 do PCMSO"

---

## Público-Alvo

### Usuários Primários

#### 1. Clínicas de Medicina do Trabalho
- Médicos do trabalho que atendem múltiplas empresas
- Técnicos de enfermagem que agendam exames
- Gestores que precisam responder dúvidas de clientes

#### 2. SESMT (Serviço Especializado em Segurança e Medicina do Trabalho)
- Engenheiros de segurança do trabalho
- Técnicos de segurança do trabalho
- Médicos e enfermeiros do trabalho internos

#### 3. Departamentos de RH
- Analistas de RH responsáveis por admissões
- Gestores de benefícios e medicina ocupacional
- Coordenadores de compliance trabalhista

### Usuários Secundários

- Auditores internos e externos
- Consultores em segurança do trabalho
- Advogados trabalhistas
- Gestores operacionais que precisam entender riscos de suas equipes

---

## Funcionalidades do MVP

### Funcionalidade 1: Consulta de Riscos por Cargo

**Descrição:** Permite identificar todos os riscos ocupacionais associados a um cargo específico.

**Entrada:** Nome do cargo ou função  
**Saída:** Lista de riscos com classificação (Ergonômico, Mecânico, Elétrico, etc.) e descrição dos danos à saúde

**Exemplo:**
```
Usuário: "Quais os riscos do cargo de soldador?"

Resposta: 
- Risco FÍSICO: Exposição a radiação não ionizante (arco elétrico)
- Risco QUÍMICO: Fumos metálicos
- Risco ERGONÔMICO: Postura inadequada durante soldagem
- Risco MECÂNICO: Projeção de partículas incandescentes
```

### Funcionalidade 2: Consulta de Exames por Cargo

**Descrição:** Lista todos os exames ocupacionais obrigatórios para um cargo, incluindo periodicidade.

**Entrada:** Nome do cargo  
**Saída:** Exames (admissional, periódico, demissional), periodicidade e tipo de exame

**Exemplo:**
```
Usuário: "Quais exames para operador de empilhadeira?"

Resposta:
- Exame Clínico: Admissional, Periódico (anual), Demissional
- Acuidade Visual: Anual
- Audiometria: Anual
- Exame Toxicológico: Conforme legislação de trânsito
```

### Funcionalidade 3: Consulta de Periodicidade de Exames

**Descrição:** Informa a frequência com que determinado exame deve ser realizado.

**Entrada:** Nome do exame  
**Saída:** Periodicidade padrão

### Funcionalidade 4: Consulta de Recomendações Especiais

**Descrição:** Identifica recomendações específicas do PCMSO (gestantes, menores, portadores de necessidades especiais, etc.)

**Entrada:** Grupo ou condição específica  
**Saída:** Recomendações e restrições aplicáveis

### Funcionalidade 5: Busca por Setor

**Descrição:** Lista todos os cargos de um setor específico.

**Entrada:** Nome do setor  
**Saída:** Cargos, quantidade de colaboradores

### Funcionalidade 6: Informações da Empresa

**Descrição:** Retorna dados cadastrais da empresa e informações do PCMSO.

**Entrada:** Pergunta sobre a empresa  
**Saída:** Razão social, CNPJ, CNAE, grau de risco, vigência do programa, médico responsável

---

## Casos de Uso Práticos

### Caso 1: Admissão de Novo Colaborador

**Situação:** Analista de RH precisa agendar exames admissionais para um novo motorista.

**Fluxo:**
1. Analista pergunta: "Quais exames admissionais para motorista?"
2. SafetyDoc AI lista todos os exames obrigatórios
3. Analista agenda com a clínica ocupacional

**Benefício:** Reduz tempo de consulta de 10-15 minutos para menos de 1 minuto.

---

### Caso 2: Planejamento de Exames Periódicos

**Situação:** Técnico de segurança precisa planejar os exames periódicos do mês.

**Fluxo:**
1. Técnico pergunta: "Quais cargos têm exames com periodicidade anual?"
2. SafetyDoc AI lista os cargos e exames
3. Técnico gera cronograma de convocação

**Benefício:** Evita atrasos e não conformidades.

---

### Caso 3: Resposta Rápida em Auditoria

**Situação:** Durante auditoria fiscal, auditor questiona sobre riscos de determinado cargo.

**Fluxo:**
1. Gestor pergunta: "Quais riscos para auxiliar administrativo?"
2. SafetyDoc AI retorna lista com citação da seção do PCMSO
3. Gestor apresenta evidência ao auditor

**Benefício:** Agilidade e rastreabilidade na resposta.

---

### Caso 4: Esclarecimento para Gestores Operacionais

**Situação:** Gerente de produção quer entender porque certo exame é exigido.

**Fluxo:**
1. Gerente pergunta: "Por que audiometria é obrigatória para operador de prensa?"
2. SafetyDoc AI explica o risco de exposição a ruído e referencia a NR-07
3. Gerente compreende a importância

**Benefício:** Educação e conscientização sobre saúde ocupacional.

---

## Estrutura de Dados

O SafetyDoc AI organiza internamente as informações em **4 abas relacionais**:

### Aba 1: Empresa

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| id_empresa | Identificador único | 1 |
| razao_social | Nome completo da empresa | CIRURGICA FONTELLES COMERCIO E REPRESENTACOES LTDA |
| cnpj | CNPJ da empresa | 12.345.678/0001-90 |
| cnae | Código CNAE principal | 47.73-3-00 |
| grau_risco | Grau de risco da atividade | 3 (Grau Médio) |
| endereco | Endereço completo | Av. Exemplo, 123 - São Luís/MA |
| num_profissionais | Total de colaboradores | 25 |
| medico_pcmso | Médico coordenador do PCMSO | Dr. João Silva - CRM 12345/MA |
| vigencia_inicio | Data de início da vigência | 01/01/2025 |
| vigencia_fim | Data de término da vigência | 31/12/2025 |

---

### Aba 2: Cargos

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| id_empresa | Referência à empresa | 1 |
| razao_social | Nome da empresa | CIRURGICA FONTELLES... |
| setor | Departamento/setor | ADMINISTRATIVO |
| cargo | Nome da função | AUXILIAR ADMINISTRATIVO |
| quantidade | Número de colaboradores no cargo | 3 |

---

### Aba 3: Riscos

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| id_empresa | Referência à empresa | 1 |
| razao_social | Nome da empresa | CIRURGICA FONTELLES... |
| tipo_risco | Classificação do risco | ERGONÔMICO |
| descricao_risco | Detalhamento do risco | Postura inadequada durante digitação |
| danos_saude | Possíveis danos à saúde | LER/DORT, dores musculares |

**Tipos de Risco Suportados:**
- Ergonômico
- Mecânico
- Elétrico
- Altura
- Psicossocial
- Físico
- Químico
- Biológico

---

### Aba 4: Exames

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| id_empresa | Referência à empresa | 1 |
| razao_social | Nome da empresa | CIRURGICA FONTELLES... |
| exame | Tipo de exame | Audiometria |
| periodicidade | Frequência de realização | Anual |

**Exames Comuns:**
- Exame Clínico Ocupacional
- Hemograma Completo
- Glicemia
- ECG (Eletrocardiograma)
- Radiografia de Coluna
- Acuidade Visual
- Audiometria
- Espirometria
- Exame Toxicológico

---

## Diferenciais Competitivos

### 1. Especialização em Saúde Ocupacional
Diferente de assistentes genéricos, o SafetyDoc AI foi desenvolvido especificamente para o contexto brasileiro de SST, compreendendo:
- Terminologia técnica da área
- Estrutura típica de PCMSOs
- Relação entre cargos, riscos e exames
- Referências a NRs quando aplicável

### 2. Rastreabilidade Total
Toda resposta é acompanhada da citação da fonte (seção, tabela, página), permitindo validação e auditoria.

### 3. Tom Técnico-Acessível
O assistente equilibra rigor técnico com didática, sendo compreensível tanto para especialistas quanto para gestores não técnicos.

### 4. Base em Dados Estruturados
Ao contrário de soluções que fazem OCR direto em PDFs, o SafetyDoc AI trabalha com dados previamente estruturados, garantindo:
- Maior precisão nas respostas
- Consultas mais rápidas
- Possibilidade de cruzamento de informações

### 5. Zero Especulação
O assistente **nunca** inventa informações. Se não houver dados na base, ele declara explicitamente a limitação.

### 6. Roadmap com Automação (Visão Futura)
Diferencial estratégico: capacidade de expandir para pipeline completo de extração automática de PDFs.

---

## Limitações e Escopo

### O que o SafetyDoc AI NÃO faz (MVP):

#### 1. Não Calcula Dimensionamentos
- Não calcula dimensionamento de SESMT
- Não determina necessidade de CIPA
- Não faz cálculos de insalubridade/periculosidade

#### 2. Não Cria Documentos Novos
- Não elabora laudos ou pareceres técnicos
- Não gera ASOs (Atestados de Saúde Ocupacional)
- Não cria novos PCMSOs

#### 3. Não Substitui Parecer Médico
- Não faz diagnósticos
- Não interpreta resultados de exames
- Não emite recomendações médicas personalizadas

#### 4. Não Acessa Sistemas Externos
- Não se conecta ao eSocial
- Não integra com prontuários eletrônicos
- Não acessa sistemas de RH/folha

#### 5. Não Interpreta Legislação Completa
- Limita-se ao que está descrito no PCMSO
- Não consulta NRs em tempo real
- Não acompanha mudanças legislativas

### Requisitos da Base de Dados (MVP):

- **Documento de entrada:** PCMSO já estruturado em planilha Excel com 4 abas (Empresa, Cargos, Riscos, Exames)
- **Formato:** Dados tabulares conforme especificação técnica
- **Escopo:** Uma empresa por consulta (multi-empresa em versões futuras)

---

## Roadmap Futuro

### Fase 2: Pipeline de Extração Automática (Q2/2026)

**Objetivo:** Eliminar a necessidade de estruturação manual de dados.

**Componentes:**
1. **Extrator de PDFs**
   - Motor de OCR otimizado para PCMSOs
   - Reconhecimento de padrões de layout
   - Extração de tabelas e seções
   - Tratamento de variações de formato

2. **Validação e Limpeza**
   - Detecção de inconsistências
   - Sugestão de correções
   - Normalização de nomenclaturas

3. **Banco de Dados PostgreSQL**
   - Migração de Excel para banco relacional
   - Performance otimizada para consultas
   - Histórico de versões de documentos

**Benefício:** Empresas poderão enviar PDFs diretamente e ter o assistente operacional em minutos.

---

### Fase 3: Multi-Documento (Q3/2026)

**Objetivo:** Cruzar informações de múltiplos documentos.

**Funcionalidades:**
- Integração PCMSO + PPRA/PGR (Programa de Gerenciamento de Riscos)
- Integração PCMSO + PCMAT (para construção civil)
- Validação cruzada: riscos do PPRA vs. exames do PCMSO
- Detecção de gaps: cargos com riscos sem exames correspondentes

---

### Fase 4: Dashboards e Relatórios (Q4/2026)

**Objetivo:** Visualização gerencial de dados.

**Componentes:**
- Dashboard de riscos por setor
- Dashboard de exames vencidos/a vencer
- Relatórios de compliance
- Exportação customizável

---

### Fase 5: Integrações Externas (2027)

**Objetivo:** Conectar com ecossistema de sistemas corporativos.

**Integrações:**
- eSocial (eventos S-2220 e S-2240)
- Sistemas de prontuário eletrônico
- ERPs de folha de pagamento
- Plataformas de agendamento de exames

---

### Fase 6: IA Preditiva (2027+)

**Objetivo:** Análise preditiva e recomendações proativas.

**Funcionalidades:**
- Previsão de exames a vencer
- Identificação de padrões de afastamento
- Sugestão de ações preventivas
- Benchmarking entre empresas do mesmo setor

---

## Tecnologias Utilizadas

### MVP (Atual)

**Backend de Dados:**
- Python 3.x
- Pandas (manipulação de dados)
- PDFPlumber (leitura de PDFs - fase futura)
- OpenPyXL (geração de Excel)

**Assistente IA:**
- Google NotebookLM
- Técnicas de Prompt Engineering:
  - Role-Playing (personificação do especialista)
  - Few-Shot Learning (exemplos práticos)
- Base de conhecimento: Excel estruturado

**Formato de Saída:**
- Markdown
- Excel (.xlsx)

---

### Fases Futuras

**Banco de Dados:**
- PostgreSQL (relacional)
- Prisma ORM

**Backend:**
- Python FastAPI
- Docker para containerização

**Frontend (opcional):**
- React.js
- Dashboard com Chart.js ou Recharts

**Infraestrutura:**
- AWS ou Google Cloud
- CI/CD com GitHub Actions

---

## Conclusão

O **SafetyDoc AI** representa uma evolução significativa na forma como profissionais de saúde e segurança do trabalho acessam e utilizam informações críticas contidas em PCMSOs.

### Proposta de Valor

✅ **Economia de Tempo:** De 10-15 minutos por consulta para menos de 1 minuto  
✅ **Redução de Erros:** Informações precisas com rastreabilidade  
✅ **Democratização do Conhecimento:** Linguagem acessível para não especialistas  
✅ **Compliance Facilitado:** Respostas rápidas em auditorias  
✅ **Escalabilidade:** Roadmap claro para automação completa  

### Visão de Longo Prazo

Tornar-se a **plataforma de referência** em inteligência aplicada à gestão de saúde ocupacional no Brasil, integrando extração automatizada de documentos, análise preditiva e integração com o ecossistema de SST.

---

## Sobre Este Documento

**Versão:** 1.0  
**Data:** Fevereiro de 2026  
**Autor:** SafetyDoc AI - Projeto de Especialização em IA  
**Contexto:** Desafio Fase 1 - Rocketseat - IA Generativa e Alta Performance  

---

**SafetyDoc AI** - Inteligência em Saúde do Trabalho  
*Transformando dados ocupacionais em conhecimento acessível*