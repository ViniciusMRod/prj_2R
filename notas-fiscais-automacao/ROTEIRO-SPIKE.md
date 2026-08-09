# Roteiro do spike — login + seletores (versão para implementar in loco)

Sessão presencial única que resolve os dois pontos que travam a Fase 2 (ver
README): confirmar o login com certificado e capturar os seletores reais do
formulário. Feita no **notebook da analista do 2R** — é o único computador
onde o certificado está instalado e a única máquina onde este robô poderá
rodar em produção (confirmado pelo 2R em 31/07).

Este roteiro é para SAIR de lá com `preencher_nota()` (em
`src/robo_emissao.py`) já funcionando contra os seletores reais, não só com
anotações para transcrever depois.

**Atualização (07-08/08): boa parte do fluxo já está mapeada.** O 2R
mandou dois vídeos do preenchimento real na tela. As tabelas abaixo já
vêm com o NOME do campo confirmado — falta só o SELETOR (id/name/texto
exato pro Playwright), não mais "descobrir se o campo existe". Ver
README, seção "Rodada 4", para o achado mais importante: **o download do
PDF pós-emissão passa por hCaptcha** — não dá pra automatizar, precisa de
clique humano ali também, não só no "Emitir".

---

## 0. Preparação — antes de ir

- [ ] Levar o notebook com o repositório `notas-fiscais-automacao` já
      clonado/atualizado.
- [ ] **No seu notebook, antes de sair de casa**: rodar
      `pip install -r requirements.txt` e `playwright install chromium`.
      O download dos navegadores do Playwright é ~150-300 MB — não depender
      do wifi do 2R para isso no dia.
- [ ] Combinar previamente com a analista/2R: o Plano A (melhor opção, ver
      abaixo) exige instalar Python + Playwright **temporariamente** no
      notebook dela, porque é lá que o certificado mora. Perguntar se há
      alguma restrição de TI antes de chegar — evita perder a viagem.
- [ ] Se instalar algo no notebook dela não for possível: ir direto para o
      **Plano B** (não precisa instalar nada, mas não testa o login
      automatizado de verdade — ver comparação abaixo).
- [ ] Separar com a analista 2-3 notas REAIS que ela já ia emitir naquele
      dia — idealmente uma com retenção de ISS, uma sem, e uma para CPF se
      der. São o material de teste; evita ter que simular dado fictício.
- [ ] Deixar `src/robo_emissao.py` aberto num editor, pronto para colar os
      seletores conforme forem descobertos.

---

## Plano A (recomendado) — Playwright Codegen, no notebook dela

O Playwright tem um gravador embutido: você navega manualmente pela tela
(login, preenche o formulário) e ele **gera o código Python com os seletores
corretos sozinho**, em tempo real, numa janela ao lado. É o jeito mais rápido
de sair de lá com código pronto, não só anotações.

No notebook dela, com o repositório clonado e o ambiente instalado
(`pip install -r requirements.txt && playwright install chromium`):

```bash
playwright codegen "https://www.nfse.gov.br/EmissorNacional/Login?ReturnUrl=%2fEmissorNacional%2f"
```

Isso abre DUAS janelas:

1. O **navegador** — onde você (ou a analista) navega normalmente.
2. O **Playwright Inspector** — onde o código Python vai aparecendo sozinho
   conforme você clica e digita na primeira janela.

Fluxo:

- Deixe a **analista fazer o login com o certificado dela** nessa janela.
  Funcionando ou não, ANOTE o que aconteceu — é o teste mais importante do
  spike (ver seção 1).
- Depois do login, navegue pelo fluxo completo de UMA nota de teste,
  seguindo as seções 2 a 7 abaixo, passo a passo.
- A cada campo preenchido, o Inspector mostra a linha equivalente (por
  exemplo `page.fill("#documentoTomador", "12345678000195")` ou
  `page.get_by_label("CNPJ/CPF").fill(...)`) — **é isso que você copia** para
  a tabela de cada seção.
- Pare ANTES de clicar em "Emitir", a menos que seja uma das notas reais
  combinadas com a analista (aí deixe ela clicar, veja a seção 8).

Dica avançada: se o codegen não abrir uma janela específica que você quer
inspecionar depois de já estar logado (ex.: voltar para testar de novo o
mesmo campo), dá para chamar `page.pause()` num script Python qualquer — abre
o mesmo Inspector no meio da execução, sem precisar regravar do zero.

---

## Plano B (sem instalar nada) — DevTools manual, navegador dela mesma

Se não for possível instalar Python/Playwright no notebook dela:

- Ela loga normalmente no navegador que já usa no dia a dia.
- Você abre o DevTools (tecla **F12**) na aba de emissão.
- Para cada campo: clique com o botão direito no elemento na TELA →
  "Inspecionar" → no painel do DevTools, com a tag HTML já destacada, clique
  direito nela → "Copy" → "Copy selector" (funciona igual no Chrome e no
  Edge).
- Cole o seletor copiado na tabela da seção correspondente abaixo.

**Diferença importante**: este plano NÃO valida se o Playwright consegue
autenticar sozinho com o certificado — só confirma os seletores do
formulário. Vai ser preciso uma segunda sessão curta, só para testar o login
automatizado, antes de confiar o robô para rodar sem supervisão.

---

## 1. Login (o teste mais importante — fazer primeiro, sempre)

- Abra a URL de login (Plano A: pelo próprio `playwright codegen`; Plano B:
  no navegador normal dela) no notebook dela. Tela de entrada tem dois
  botões: "Acessar com certificado digital" e "Acessar via GOV.BR" — usar
  o primeiro.
- Confirme: autentica sozinho, ou ainda aparece um seletor de certificado do
  Windows para escolher/confirmar? No vídeo do fluxo manual, do clique até
  o Dashboard carregado foram uns 5 segundos, sem prompt de senha visível
  — mas isso ainda não foi testado com o Chromium do Playwright (Plano A).
- Anote: quantos cliques até logar; quanto tempo leva; se aparece algum
  aviso de segurança do navegador.
- **Se isso não funcionar de jeito nenhum no Plano A**, é o único cenário
  que reabre a decisão RPA vs. API oficial do governo (ver README, seção
  "Decisões técnicas") — pare o roteiro aqui e volte para discutir antes de
  seguir capturando seletores que talvez não sirvam.

---

## 2. Pessoas (emitente / tomador)

Com uma nota de teste (ou observando a analista abrir uma real):

| Campo confirmado | Seletor a capturar | Observação |
|---|---|---|
| "Você irá emitir esta NFS-e como?" Prestador/Tomador/Intermediário | | sempre Prestador |
| Botão "Exibir detalhes do emitente" | | expansível, opcional |
| "Onde está localizado o estabelecimento/domicílio?" Tomador não informado/Brasil/Exterior | | sempre Brasil |
| Campo CPF/CNPJ do tomador | | |
| Botão da lupinha (busca o cadastro) | | |
| Razão social (vem readonly) | | confirmar que vem preenchida sozinha |
| CEP / endereço | | **já confirmado automático** (2R, 31/07 — vídeo confirma visualmente) |

- Teste com um **CPF**, não só CNPJ — 6 empresas da planilha são pessoa
  física. Confirme se a busca automática (razão social + endereço) também
  funciona para CPF.

---

## 3. Serviço

| Campo confirmado | Seletor a capturar | Observação |
|---|---|---|
| "É caso de imunidade, exportação de serviço ou não incidência do ISSQN?" Não/Sim | | **campo novo, não documentado antes do vídeo** — sempre Não |
| Código de Tributação Nacional (17.01.01) | | dropdown pesquisável |
| "Município de incidência do ISSQN" | | readonly, auto-preenchido |
| Descrição do Serviço | | |
| Item NBS | | rótulo em `NBS_ITEM_ROTULO` veio do passo a passo textual, ainda não confirmado contra a tela |

---

## 4. Valores

| Campo confirmado | Seletor a capturar | Observação |
|---|---|---|
| "Valor do serviço prestado" | | **formato CONFIRMADO com vírgula** ("1.595,00") — já corrigido no código |

---

## 5. Tributação Municipal / Retenção de ISS — a parte mais rica

| Campo confirmado | Seletor a capturar | Observação |
|---|---|---|
| "Retenção do ISSQN pelo Tomador ou pelo Intermediário?" Sim/Não | | |
| "Informe abaixo por quem o imposto será retido" — Retido pelo Tomador / Retido pelo Intermediário | | **campo novo**: é escolha de QUEM retém, não um Sim/Não simples. Sempre "pelo Tomador" nas 274 |
| "Informe o valor da alíquota" (%) | | **CONFIRMADO editável**, formato vírgula ("4,19"). Portal avisa piso de 1,8% para ME/EPP no Simples Nacional |
| "Este serviço está amparado por algum benefício municipal?" Não/Sim | | **campo novo** — sempre Não |
| "Será aplicado algum tipo de Dedução/Redução à base de cálculo do ISSQN?" Não/Sim | | **campo novo** — sempre Não |
| BC ISSQN / ISSQN Apurado (calculados) | | só para conferência visual contra `calcular_iss()` |

- Marque "SIM" numa nota de teste e confirme que os 4 campos novos acima
  aparecem exatamente nessa ordem.
- Compare o que a tela calcula com `calcular_iss()` do código — o caso real
  já confirmado é R$ 243,00 × 4,19% = R$ 10,18 de ISSQN, líquido R$ 232,82.

---

## 6. Tributação Federal / Valor aproximado dos tributos

| Campo confirmado | Seletor a capturar | Observação |
|---|---|---|
| "Situação Tributária do PIS/COFINS" | | combobox pesquisável, sempre "00 - Nenhum" |
| "Tipo de retenção do PIS/COFINS/CSLL" | | **campo novo**, sempre "PIS/COFINS/CSLL Não Retidos" |
| IRRF / Contribuições Sociais-Retidas / Contribuição Previdenciária-Retida | | sempre vazios nos casos vistos |
| "Valor aproximado dos tributos" (Federal/Estadual/Municipal %) | | **NÃO CONFIRMADO se é por nota ou config de conta** — apareceu já preenchido (0,90/0,10/0,00) no vídeo. Perguntar/observar se essa tela aparece toda vez |

Seletores finais antes da tela de revisão.

---

## 7. Tela de revisão — não emitir a menos que seja nota real

- Print da tela de revisão final, para conferência.
- Se for uma das notas reais combinadas com a analista: deixe ela clicar em
  "Emitir" e observe o passo 8.
- Se for só uma nota de teste fictícia: **pare aqui, não emita.**

## 8. Depois de emitir (só em nota real) — hCaptcha confirmado aqui

**Já sabemos o que acontece** (vídeo do 2R, 07/08): a tela de sucesso tem
botões "Baixar XML" / "Baixar DANFSe" / "Visualizar NFS-e" / "NFS-e
emitidas" / "Nova NFS-e". Clicar em baixar abre um modal "VALIDAÇÃO DE
USUÁRIO" com **hCaptcha** — checkbox "Sou humano" + desafio de imagem
("selecione os animais que nascem de ovos", ou similar).

- **Não é possível automatizar o download** — resolver captcha
  automaticamente está fora de questão (viola termos do hCaptcha/portal).
  O `input()` em `emitir_lote` já foi ajustado para pedir o clique humano
  também nessa etapa, não só no Emitir.
- O que ainda falta observar: o captcha aparece **sempre** que se clica em
  baixar, ou só às vezes? E qual nome de arquivo o navegador sugere ao
  salvar o DANFSe (para comparar com `montar_nome_pdf`)?

---

## Depois: como levar os seletores para o código

Mapa de qual placeholder em `preencher_nota()` (arquivo
`src/robo_emissao.py`) cada seletor capturado substitui:

| Hoje (placeholder no código) | Campo real | Seletor capturado no spike |
|---|---|---|
| `page.click("text=Emissão Completa")` | tipo de emissão | |
| `page.click("#casoImunidadeExportacao_nao")` | imunidade/exportação/não incidência | |
| `page.fill("#documentoTomador", ...)` | CNPJ/CPF do tomador | |
| `page.click(f"text={CODIGO_TRIBUTACAO_NACIONAL}")` | código de serviço 17.01.01 | |
| `page.fill("#descricaoServico", ...)` | descrição do serviço | |
| `page.click(f"text={NBS_ITEM_ROTULO}")` | item NBS | |
| `page.fill("#valorNota", ...)` | valor da nota (vírgula, já corrigido) | |
| `page.click("#retencaoIssSim")` / `page.click("#retencaoIssNao")` | toggle retenção ISS | |
| `page.click("#retidoPeloTomador")` | por quem é retido | |
| `page.fill("#aliquotaIss", ...)` | alíquota (editável, vírgula) | |
| `page.click("#beneficioMunicipal_nao")` | benefício municipal | |
| `page.click("#deducaoReducao_nao")` | dedução/redução | |
| `page.click(f"text={REGIME_APURACAO_TRIBUTOS.upper()}")` | regime tributário | |
| `page.select_option("#situacaoPisCofins", "00")` | situação PIS/COFINS | |
| `page.select_option("#tipoRetencaoPisCofinsCsll", "NAO_RETIDOS")` | tipo de retenção PIS/COFINS/CSLL | |

Com a tabela preenchida, é essencialmente um find-and-replace dentro de
`preencher_nota()` — a lógica em volta (validações, cálculo do ISS,
mensagens de conferência) não precisa mudar, só os seletores.

Se o codegen (Plano A) gerou um jeito diferente de localizar o campo — por
exemplo `page.get_by_label("CNPJ/CPF")` em vez de `page.fill("#id", ...)` —
tudo bem usar o que o codegen gerou: geralmente é mais robusto a mudanças
futuras no portal do que um `#id` fixo. Prefira o código gerado ao invés de
tentar adivinhar um seletor equivalente de cabeça.

## Ao voltar

- Revisar o diff (`git diff src/robo_emissao.py`) antes de qualquer commit —
  seletor capturado no calor da hora merece uma segunda leitura fria, sem
  pressa.
- Rodar `python -m py_compile src/robo_emissao.py` para garantir que nada
  ficou com erro de sintaxe.
- Atualizar a docstring do módulo (topo do arquivo): os itens "NÃO EXECUTAR
  antes de..." relacionados a seletores e login deixam de ser TODO assim que
  confirmados.

---

## Enquanto estiver lá, aproveitar para confirmar ao vivo

Bloco 1 respondido por texto e boa parte da Rodada 4 já fechada por vídeo
— o que resta é mais rápido ver acontecendo do que perguntar por WhatsApp:

- Os rascunhos parados no portal (pergunta 14 do Bloco 2) — quantos tem
  agora, o que a analista faz com eles.
- "Valor aproximado dos tributos" — essa tela aparece em TODA nota, ou só
  configura uma vez por conta? (ver seção 6)
- O hCaptcha do download — aparece sempre, ou só em algumas notas?
- Vencimento vazio de `AUTO TECH SOLUCOES LTDA` na `v03` (regressão da
  célula mesclada) — já pode avisar a analista ali mesmo.

---

## Cuidados

- Nunca clicar em "Emitir" numa nota que não seja real e combinada
  previamente com a analista.
- Nunca abrir, copiar ou mover o arquivo `.pfx` do certificado — o robô (e
  este roteiro) nunca precisam tocar nele diretamente, só usar o navegador
  que já enxerga o certificado instalado no Windows.
- Se instalar Python/Playwright no notebook dela (Plano A) e a política de
  TI do 2R pedir para não deixar nada instalado depois: desinstalar ao
  final da sessão.

## Saída esperada do spike

`preencher_nota()` com seletores reais no lugar dos placeholders, testado
manualmente contra pelo menos uma nota real de cada tipo (com e sem
retenção de ISS, e se possível uma PF). Depois disso a Fase 2 deixa de ser
esqueleto.
