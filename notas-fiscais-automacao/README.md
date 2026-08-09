# Automação de emissão de NFS-e — 2R

Automação (semi-automatizada, com revisão humana) da emissão mensal de
**274 notas fiscais de serviço** (R$ 90.383,49/mês) do 2R no Emissor
Nacional de NFS-e (nfse.gov.br). Ferramenta a ser entregue para a equipe
do 2R operar e manter — este repositório não fica em operação recorrente
do consultor.

Contexto completo, veredito de viabilidade e decisões técnicas:
`Vini_Vault/Project_2R/notasFiscais/analise-automacao/` (relatório do
council + transcript).

## Status: Fase 1 FECHADA (0 erros) — Fase 2 falta um único acesso

`validar_planilha.py` roda **sem erros bloqueantes** contra a planilha do
2R desde `PLANILHA ATUALIZADA_v02.xlsx` (31/07) — as 4 correções de CNPJ
pedidas no Bloco 1 fecharam o gate da Fase 1. `src/robo_emissao.py`
segue **esqueleto não executável**, mas os dois pontos que travam a
Fase 2 colapsaram numa única causa: ninguém aqui ainda entrou na tela
autenticada do portal.

- **Login com certificado**: bem menos arriscado do que parecia na
  rodada 1, e a resposta do 2R (31/07) simplificou ainda mais. O
  certificado A1 está instalado só no **notebook da analista**, não pede
  mais senha/PIN a cada acesso, e só ela emite hoje — um único operador,
  uma única máquina. Não é um `.pfx` que o robô precisaria carregar ou
  assinar em código. Rodando o Chromium em modo visível NESSE NOTEBOOK,
  o Windows deve autenticar sozinho (ou no máximo mostrar o seletor
  nativo, se houver mais de um certificado instalado); o `input()` que já
  existe no código foi desenhado para esse passo manual. Ainda não foi
  **observado** acontecendo — é o primeiro teste do spike, mas a
  probabilidade de funcionar de primeira subiu bastante sem a senha.
- **Seletores do formulário**: os PDFs confirmaram os *valores*, não os
  *campos*. Só se resolve olhando o DOM autenticado. Uma coisa a MENOS
  para capturar: o 2R confirmou que o portal preenche o **endereço do
  tomador sozinho** a partir do CNPJ/CPF — não precisa mapear um fluxo de
  CEP manual, e não é preciso coletar endereço das 274 empresas.

Os dois se resolvem na MESMA sessão — ver `ROTEIRO-SPIKE.md`.

### O que a rodada 2 resolveu

- Valor faltante: **resolvido** (274/274 linhas com valor numérico).
- 16 vencimentos faltantes: **15 resolvidos**; o 16º (L21) estava em
  **célula mesclada** — não era dado faltando. O validador agora resolve
  merges e avisa.
- Retenção de ISS: **3 empresas**, alíquota 0,0419 (4,19%), confirmada
  contra o DANFSe real (243,00 × 4,19% = 10,18; líquido 232,82).
- 6 registros sem CNPJ: o cliente confirmou emissão para **CPF**; há 6
  CPFs com DV válido. Não são os mesmos 6 registros — 4 sumiram da planilha.
- Descrição padrão: confirmada em três fontes (fala do cliente, PDF, L3).
- Duplicata do CNPJ do emitente: **resolvida pela metade** — uma linha foi
  corrigida, a outra (L52) continuava com o CNPJ do próprio emitente.
- Campos fixos do emitente e do serviço: todos extraídos dos DANFSe e já
  em `src/dados_cliente.py` (não versionado — ver seção Configuração).

### O que a rodada 3 resolveu (respostas do Bloco 1, 31/07)

Todas as 4 correções de CNPJ pedidas vieram exatas — inclusive as duas
reconstruções de dígito verificador que o validador só tinha *sugerido*:

| Linha | Tipo de erro | Desfecho |
|---|---|---|
| L52 | tomador com o CNPJ do próprio emitente | corrigido para o CNPJ real do tomador |
| L106 | CNPJ duplicado com outra empresa (arrasto de célula) | corrigido; a duplicidade sumiu |
| L143 | CNPJ truncado (13 dígitos) | corrigido — bateu exatamente com o DV que o validador calculou |
| L228 | CNPJ truncado (13 dígitos) | corrigido — idem |

Diff v01→v02 conferido linha a linha: só essas 4 células mudaram, nada
mais. `validar_planilha.py` contra a planilha v02:
**0 ERRO / 9 AVISO** — primeira vez que a planilha fecha limpa.

Outras respostas do Bloco 1:

- **Lotes**: confirmado, ~8 lotes/mês, critério = vencimentos dos
  próximos dias, antecedência padrão de 3 a 5 dias.
- **Exceção nova**: ~50 empresas têm a nota enviada junto com o boleto e
  precisam de 10 a 12 dias de antecedência (não 3-5). O 2R vai sinalizar
  essas empresas na própria planilha — coluna ainda não existe, ver
  pendências abaixo.
- **Endereço**: confirmado, o portal preenche sozinho a partir do
  CNPJ/CPF. Risco de "faltam 274 endereços" **fechado**.
- **Certificado**: confirmado, notebook da analista, sem senha, operador
  único. Ver seção de Status.
- **274 empresas**: confirmado como base de faturamento; as 19 que
  saíram são churn real. O 2R já avisou que a lista vai continuar
  mudando — é por isso que o roster do validador existe (ver `Uso`).

Avisos que continuam de pé (não bloqueiam): 3 descrições com
`COMPETÊNCIA:` em branco (L35, L36, L37), um mesmo CPF em 2 linhas
(L161/L162 — provavelmente legítimo, pessoa física com dois
estabelecimentos), 4 cadastros "MATRIZ E FILIAIS" agregados num só CNPJ
(L233, L235, L236, L237), e a célula mesclada de L21.

## Configuração (primeira vez numa máquina)

Os dados que identificam o prestador — CNPJ, razão social, inscrição
municipal, telefone, e-mail, código de serviço — ficam em
`src/dados_cliente.py`, que **não é versionado**. Este repositório é
público e esses são dados de um terceiro real.

```bash
cp src/dados_cliente.example.py src/dados_cliente.py
# preencher com os dados reais — todos estão nos PDFs (DANFSe) de notas
# já emitidas pelo cliente
```

Sem esse arquivo, os dois programas param na hora com uma mensagem
explicando o que fazer, em vez de rodar com dados errados.

O mesmo vale para a planilha de controle e os PDFs de notas: são dados do
cliente, ficam fora do repositório (`*.xlsx`, `*.pdf` e `*.json` já estão
no `.gitignore` da raiz).

## Uso

```bash
pip install -r requirements.txt

# Fase 1 — rodar SEMPRE antes de qualquer emissão
python src/validar_planilha.py "caminho/da/planilha.xlsx"
```

Exit code **0** = sem erros bloqueantes; **1** = corrigir antes de emitir.
Esse exit code é o portão da Fase 2 e deve constar do contrato: a
responsabilidade pela correção cadastral é do 2R.

## Decisões técnicas

Mantidas da rodada 1:

- **RPA sobre a interface web**, não integração com o webservice oficial
  (ADN) — para não mover a custódia do certificado digital. O motivo
  sempre foi custódia, nunca ISS; nada nos dados novos reabre isso.
- **Sempre semi-automatizado**: o robô preenche e para; a emissão final é
  um clique humano. Com 274 notas o cliente vai pedir 100% automático —
  esse clique é a única barreira que sobrevive a todos os outros modos de
  falha.
- **Formato comercial**: projeto fechado (Fase 1 + Fase 2), manutenção
  mensal separada e opcional.

Novas nesta rodada:

- **O robô não clica em "Emitir"** (o esqueleto antigo clicava): o Enter
  no terminal apenas libera a próxima nota.
- **Registro de emissão por lote** (`emitidas_NN.json` na pasta de saída,
  gravado a cada nota): retomar um lote interrompido não reemite o que já
  saiu. NFS-e duplicada não se desfaz com um clique — cancelamento tem
  prazo e a nota já compôs a receita da competência.
- **Conferência de totais** antes de abrir o navegador (nº de notas, soma,
  maior nota, quantas com retenção) exigindo confirmação digitada.
- **Coluna esperada que some do cabeçalho é ERRO**, não observação. Antes
  falhava aberto: renomear as duas colunas de ISS emitiria as 3 notas com
  retenção como isentas, em silêncio e com exit code 0.
- **Duplicidade de documento também é checada no robô** (checagem cruzada
  entre linhas), não só no validador — os dois programas são executados de
  forma independente.
- **Duplicata só é rebaixada a AVISO com nome-base idêntico.** A regra de
  similaridade aproximada anterior tratava "JOSÉ FELIPE" x "JOSÉ LUCAS
  SILVA BORGES" e matriz x filial como mesmo titular — exatamente as
  vizinhanças onde o arrasto de célula no Excel repete o CNPJ.
- **Precificar a engenharia fixa, nunca por empresa.** O esforço do robô
  é ~90% independente do volume: o validador processou 274 linhas sem uma
  linha de código a mais.
- **RPA vs. API oficial (ADN), revisitado**: o certificado já morar na
  máquina do 2R **não muda essa recomendação**, mas muda o motivo. A API
  oficial (DPS → NFS-e) normalmente exige **assinatura digital do XML** da
  nota com a chave privada do certificado — confiança moderada, não
  verificado a fundo — uma operação bem mais sensível do que um login de
  navegador, que é mediado pelo Windows/Chromium sem o código nunca tocar
  a chave. RPA sobre a UI evita essa escalada de confiança porque ninguém
  além do próprio portal do governo assina a nota. Reavaliar só se o
  spike mostrar que o login via navegador não funciona na máquina do 2R.
- **Execução em lotes por vencimento — decisão fechada.** `emitir_lote()`
  já recebe uma lista de notas por chamada (o chamador agrupa por
  vencimento antes de invocar), então já é compatível com rodar ~20×/mês
  em fatias pequenas em vez de 1× com 274. Falta só um helper que agrupe
  a planilha por `dia_vencimento` — não urgente, ainda travado no spike.
- **Delivery via Claude/Cowork na máquina do 2R — ideia em aberto, não
  decidida.** Como interface de operação (a analista aciona a execução do
  script Python já determinístico por um agente local, sem abrir
  terminal) é promissora. Como *substituto* do preenchimento
  determinístico por um agente que lê a tela e digita via visão — não
  recomendado para documento fiscal: um agente por visão pode transpor
  dígito de CNPJ ou valor; o preenchimento script-a-partir-de-dado-validado
  não erra o que já passou pelo validador. Avaliar depois do spike.

## Pesquisa externa — projetos NF-e no GitHub (08/2026)

Estudo comparativo de libs open-source de emissão fiscal (PyNFe, ACBr,
sped-nfe, NFeWizard, APIs Focus NFe/NFe.io) — arquivo completo em
`Vini_Vault/Project_2R/NotasFiscais/analise-automacao/
compass_artifact_wf-2385e0db-c06a-5799-9bc7-bb160b15777d_text_markdown.md`.

**Veredito: mismatch de sistema.** Estudo cobre NF-e (SEFAZ estadual,
modelo 55) e NFS-e formato antigo ABRASF (por município). Nosso projeto é
NFS-e **Padrão Nacional** (ADN/DPS, `nfse.gov.br`) — protocolo diferente.
Nenhuma lib do estudo fala ADN/DPS. Arquitetura RPA-sobre-UI **não muda**.

O que aproveitou:

- **CNPJ alfanumérico** — produção nacional desde 06/07/2026. Ver risco
  atualizado abaixo: `validar_planilha.py` hoje mastigaria isso silencioso.
- **IBS/CBS na NFS-e — risco fechado, não aberto.** Confirmado: pra NFS-e
  o campo é **facultativo** em 2026 (NF-e modelo 55 é que é obrigatório
  desde 03/08). E pra empresa do **Simples Nacional** — regime do
  prestador — **zero obrigação até 2027**. Não entra no backlog.
- **Ambiente de homologação NFS-e Nacional** — confirmado que existe pro
  **webservice** (ADN/DPS). Não confirmado se existe URL de homologação
  pra **UI do Emissor Nacional** (o que o robô automatiza). Checar no
  spike, antes de usar nota real como fallback (ROTEIRO-SPIKE.md).
- **Lição geral (bug real do ecossistema sped-nfe, issue #941):** ambiente
  homolog/produção confundido por flag ambígua. Robô precisa deixar
  produção vs teste inequívoco, nunca uma flag que engana.
- **Confirma decisão já tomada:** não construir núcleo de emissão sobre
  MCP/API de terceiro — caso real citado no estudo, `mcp-nota-fiscal`
  ficou inviável quando a Nuvem Fiscal desativou em 31/07/2026.

## Rodada 4 — vídeos e PDFs novos (07-08/08)

O 2R mandou 2 vídeos do fluxo real de emissão, 2 PDFs de notas novas e
`PLANILHA ATUALIZADA_v03.xlsx`. Verificado abrindo os arquivos, não só
lendo a mensagem — vídeos processados via `ffmpeg` (contact sheet +
frames em pontos específicos, sem transcrever áudio).

**Achado que muda o desenho da Fase 2 — hCaptcha no download.** Depois de
emitir, a tela tem "Baixar XML" / "Baixar DANFSe" / "Visualizar NFS-e" /
"NFS-e emitidas" / "Nova NFS-e". Clicar em baixar abre um modal
"VALIDAÇÃO DE USUÁRIO" com **hCaptcha** (checkbox "Sou humano" + desafio
de imagem tipo "selecione os animais que nascem de ovos"). **Não dá para
automatizar isso** — nem deveríamos tentar (viola os termos do
hCaptcha). O clique humano do "semi-automatizado" já cobria o Emitir;
agora cobre o Emitir **e** o Baixar. Documentado em `robo_emissao.py`.

**Login: dois métodos, mais rápido do que parecia.** Tela de entrada tem
"Acessar com certificado digital" e "Acessar via GOV.BR". No vídeo, do
clique no link até o Dashboard carregado foram ~5 segundos — sem prompt
de senha visível, bate com o que a analista já tinha dito.

**Separador decimal — CONFIRMADO vírgula, risco fechado.** Valor
"1.595,00", alíquota "4,19" — todos os campos numéricos do portal usam
vírgula. `preencher_nota()` corrigido (usava ponto).

**Alíquota mínima real — 1,8%, não 2%.** O próprio portal avisa: "Para o
prestador de serviço ME/EPP... é permitido informar alíquota mínima de
1,8%". `ALIQUOTA_ISS_MINIMA_PLAUSIVEL` corrigida nos dois programas.

**Campos da tela de retenção — mais do que o esperado, todos
confirmados:** "Retido pelo Tomador" ou "pelo Intermediário" (é escolha
de quem retém, não Sim/Não simples), "amparado por benefício municipal?"
Não/Sim, "Dedução/Redução na base do ISSQN?" Não/Sim, e na aba federal
"Tipo de retenção do PIS/COFINS/CSLL" (visto sempre "Não Retidos") — nome
de campo que não existia em nenhuma documentação anterior. Aba Serviço
também tem uma pergunta antes do código de tributação: "é caso de
imunidade, exportação ou não incidência do ISSQN?" — sempre "Não".
`preencher_nota()` atualizado com os 5 campos.

**RUDINEI TOZI — fechado.** PDF real da nota "Fazenda Tozi" (CPF
708.872.763-34, R$ 260,00) confirma: são notas separadas de fato, o
próprio 2R já emite assim.

**`COMPETÊNCIA:` — fechado.** PDF real da FAPLAST mostra o texto exato:
"COMPETÊNCIA: NFS-E REFERENTE AOS SERVIÇOS REALIZADOS NO MÊS DE JULHO DE
2026" — mês por extenso, referente ao mês anterior à emissão. Já dá para
montar esse texto em código quando o agrupador de lote existir.

**Coluna de antecedência — chegou.** `v03` tem
`EMITIR 12 DIAS ANTES DO VENCIMENTO:`, 45 empresas marcadas (perto do
"~50" combinado). `validar_planilha.py` já detecta e conta essa coluna
(nome com número de dias pode mudar, busca por padrão, não texto fixo).

**Regressão nova, não pedida — reportar ao 2R.** Ao editar a planilha pra
tirar a linha de título e incluir a coluna nova, a célula mesclada que
resolvia o vencimento de `AUTO TECH SOLUCOES LTDA` (D20:D21 na v02) não
sobreviveu — em `v03` o vencimento dessa linha está vazio de verdade, não
é mais problema de leitura. Confirmado inspecionando a planilha
diretamente. Validador acusa `VENCIMENTO_AUSENTE` corretamente.

**Aberto, não confirmado:** "Valor aproximado dos tributos"
(Federal/Estadual/Municipal %) apareceu já preenchido no vídeo — parece
ser configuração da CONTA do emitente, não campo repetido por nota.
Confirmar no spike.

## Bloqueante — pedir ao 2R antes de construir a Fase 2

Bloco 1 (7 perguntas) respondido em 31/07. O que sobra:

- [ ] Vencimento vazio de verdade em `AUTO TECH SOLUCOES LTDA` na `v03`
      (regressão da célula mesclada — ver Rodada 4 acima)
- [ ] Tomadores **pessoa física**: o portal localiza cadastro por CPF?
- [ ] Raiz das pastas onde os PDFs são salvos e padrão de nome
- [ ] Os 4 cadastros "MATRIZ E FILIAIS" (L233, L235, L236, L237) são uma
      nota só ou várias? L233 é a maior nota da planilha (R$ 2.890)

Resolvidos no Bloco 1 (31/07) e na Rodada 4 (07-08/08):

- [x] ~~CPF repetido em L161/L162, são 2 notas?~~ — confirmado por PDF
      real da nota "Fazenda Tozi"
- [x] ~~Como a `COMPETÊNCIA:` é preenchida?~~ — confirmado por PDF real
      da FAPLAST, texto exato documentado acima
- [x] ~~Coluna das ~50 empresas com antecedência maior~~ — chegou na
      `v03`, 45 marcadas

- [x] ~~Correções cadastrais: L52, L105/L106, L143, L228~~ — as 4
      vieram certas, ver tabela da rodada 3 acima
- [x] ~~A coluna VENC define o agendamento?~~ — confirmado, ~8 lotes/mês
      por vencimento, mas com DUAS janelas de antecedência (ver item novo)
- [x] ~~Endereço do tomador: automático ou manual?~~ — automático,
      não precisa coletar endereço de ninguém
- [x] ~~Login com certificado: qual máquina, já instalado, pede senha,
      quantas pessoas?~~ — notebook da analista, sem senha, operador único
- [x] ~~Aceite formal de 274 empresas e churn das 19 que saíram~~ —
      confirmado; churn vai continuar e é esperado (roster do validador
      cobre isso)

## Desejável antes de entregar

- [ ] Estimativa de horas/mês do processo manual (baseline de ROI — não
      respondida em duas rodadas). Referência: **cada 1 min/nota = 4,57
      h/mês = 54,8 h/ano**
- [ ] "MES 07 / 07 DE 12" é mês do calendário ou parcela do contrato?
- [ ] Rascunhos parados no portal (5, o mais antigo de 23/06) são normais?
      Se sim, o robô pode deixar tudo como rascunho para revisão em bloco
- [ ] "Valor aproximado dos tributos" (0,90% federal / 0,10% estadual /
      0,00% municipal) é fixo para todas?
- [ ] `17.01.01` cobre as 274 empresas ou há grupos com outro item?
- [ ] Empresas fora de São Luís (Imperatriz, Pará, Pinheiro): o local de
      prestação continua São Luís/MA?
- [ ] Autorização para limpar quebras de linha nos nomes da planilha
- [ ] Quem opera o robô e quem mantém a planilha atualizada

## Pendente antes de propor ao cliente

- Limite de responsabilidade em caso de nota emitida errada
- Processo de correção/cancelamento pós-emissão (e o custo dele para o 2R)
- Plano mínimo de segurança do `.pfx` (quem acessa, como é armazenado)
- Pacote de handoff (documentação + treinamento) e **um dono nomeado** no
  2R — sem dono, a ferramenta quebra num fechamento e não volta

## Riscos conhecidos e não fechados

- **Alíquota de ISS modelada como atributo do tomador.** As 3 linhas com
  retenção têm o mesmo 0,0419 para tomadores sem relação — indício de que
  4,19% é a alíquota efetiva do **prestador** no Simples Nacional, que
  muda por competência conforme o RBT12 (que já subiu 64%). Se for isso, a
  alíquota é parâmetro mensal do lote, não cadastro.
- **Não existe competência em nenhum lugar do robô.** Se o lote rodar no
  início do mês seguinte, o portal assume a data atual e a receita fica no
  mês errado para o PGDAS-D.
- **Nada é relido do formulário.** Comparar a razão social que o portal
  resolve a partir do CNPJ com o nome da planilha é a única checagem que
  fecha a classe "CNPJ válido no DV mas de outra empresa" — nenhum
  validador offline consegue.
- ~~Separador decimal~~ — **fechado** (Rodada 4): confirmado vírgula por
  vídeo real, `preencher_nota()` corrigido.
- **CNPJ alfanumérico** — produção nacional desde 06/07/2026 (confirmado
  via pesquisa externa, 08/2026). `so_digitos()` em `validar_planilha.py`
  descarta letra e mastiga o documento SILENCIOSO — não cai limpo em
  "truncado", cai em contagem de dígito errada e mensagem enganosa.
  Nenhum caso na planilha atual (primeiro CNPJ alfanumérico do país só
  saiu 31/07/2026). Backlog: `classificar_documento` detectar letra e
  rejeitar com mensagem própria, não tratar como truncamento numérico.
- **Degradação silenciosa da planilha** é o maior risco pós-entrega: 128
  linhas foram acrescentadas por processo manual não auditado, e um
  defeito conhecido (VDC) sobreviveu a um ciclo inteiro de correção.
