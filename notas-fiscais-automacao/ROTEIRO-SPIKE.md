# Roteiro do spike — login + seletores (versão para implementar in loco)

Sessão presencial única que resolve os dois pontos que travam a Fase 2 (ver
README): confirmar o login com certificado e capturar os seletores reais do
formulário. Feita no **notebook da analista do 2R** — é o único computador
onde o certificado está instalado e a única máquina onde este robô poderá
rodar em produção (confirmado pelo 2R em 31/07).

Este roteiro é para SAIR de lá com `preencher_nota()` (em
`src/robo_emissao.py`) já funcionando contra os seletores reais, não só com
anotações para transcrever depois.

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
  no navegador normal dela) no notebook dela.
- Confirme: autentica sozinho, ou ainda aparece um seletor de certificado do
  Windows para escolher/confirmar? A analista já disse que não pede mais
  senha — mas o comportamento exato do Chromium automatizado (Plano A) ainda
  não foi observado.
- Anote: quantos cliques até logar; quanto tempo leva; se aparece algum
  aviso de segurança do navegador.
- **Se isso não funcionar de jeito nenhum no Plano A**, é o único cenário
  que reabre a decisão RPA vs. API oficial do governo (ver README, seção
  "Decisões técnicas") — pare o roteiro aqui e volte para discutir antes de
  seguir capturando seletores que talvez não sirvam.

---

## 2. Tomador do serviço

Com uma nota de teste (ou observando a analista abrir uma real):

| Campo | Seletor encontrado | Observação |
|---|---|---|
| Tipo de emissão ("Emissão Completa") | | |
| Campo CNPJ/CPF | | |
| Botão da lupinha (busca o cadastro) | | |
| Razão social (deve vir readonly) | | confirmar que vem preenchida sozinha |
| CEP / endereço | | **já confirmado como automático** (2R, 31/07) — só confirme visualmente que realmente vem preenchido, sem precisar digitar nada |

- Teste com um **CPF**, não só CNPJ — 6 empresas da planilha são pessoa
  física. Confirme se a busca automática (razão social + endereço) também
  funciona para CPF.

---

## 3. Serviço

| Campo | Seletor encontrado | Observação |
|---|---|---|
| Código de tributação (17.01.01) | | é lista suspensa ou texto livre? |
| Descrição do serviço | | |
| Item NBS | | o rótulo em `NBS_ITEM_ROTULO` no código veio do passo a passo textual, nunca confirmado contra a tela |

---

## 4. Valor

| Campo | Seletor encontrado | Observação |
|---|---|---|
| Campo de valor | | |

- Formato aceito: ponto ou vírgula decimal? O código hoje envia com ponto
  (`page.fill("#valorNota", "375.13")`) — TODO marcado em `preencher_nota`.
  Digite um valor de teste com centavos (ex.: `375,13`) e confira se o
  portal interpreta certo antes de fechar esse ponto.

---

## 5. Retenção de ISS — o campo mais importante de capturar certo

| Campo | Seletor encontrado | Observação |
|---|---|---|
| Toggle "Retenção de ISS? Sim/Não" | | |
| Campo de alíquota (se aparecer) | | |
| BC ISSQN / ISSQN Apurado (campos calculados) | | só para conferência visual |

- Marque "SIM" numa nota de teste e observe EXATAMENTE quais campos
  aparecem ou mudam na tela.
- A alíquota é **digitável** ou vem sozinha do cadastro do tomador?
  (`aliquota_iss` em `NotaFiscal` assume que é preciso informar — se o
  portal já traz do cadastro, o código de `preencher_nota` precisa mudar.)
- Compare o que a tela calcula com `calcular_iss()` do código — o caso real
  já confirmado é R$ 243,00 × 4,19% = R$ 10,18 de ISSQN, líquido R$ 232,82.

---

## 6. Regime tributário / PIS-COFINS

| Campo | Seletor encontrado | Observação |
|---|---|---|
| Regime de apuração (Simples Nacional) | | |
| Situação tributária PIS/COFINS | | hoje o código usa `select_option("#situacaoPisCofins", "00")` |

Seletores finais antes da tela de revisão.

---

## 7. Tela de revisão — não emitir a menos que seja nota real

- Print da tela de revisão final, para conferência.
- Se for uma das notas reais combinadas com a analista: deixe ela clicar em
  "Emitir" e observe o passo 8.
- Se for só uma nota de teste fictícia: **pare aqui, não emita.**

## 8. Depois de emitir (só em nota real)

- Como o PDF é entregue: download automático? aparece um botão? qual nome
  de arquivo o portal sugere?
  (resolve o TODO de `page.expect_download` em `emitir_lote`, no código)

---

## Depois: como levar os seletores para o código

Mapa de qual placeholder em `preencher_nota()` (arquivo
`src/robo_emissao.py`) cada seletor capturado substitui:

| Hoje (placeholder no código) | Campo real | Seletor capturado no spike |
|---|---|---|
| `page.click("text=Emissão Completa")` | tipo de emissão | |
| `page.fill("#documentoTomador", ...)` | CNPJ/CPF do tomador | |
| `page.click(f"text={CODIGO_TRIBUTACAO_NACIONAL}")` | código de serviço 17.01.01 | |
| `page.fill("#descricaoServico", ...)` | descrição do serviço | |
| `page.click(f"text={NBS_ITEM_ROTULO}")` | item NBS | |
| `page.fill("#valorNota", ...)` | valor da nota | |
| `page.click("#retencaoIssSim")` / `page.click("#retencaoIssNao")` | toggle retenção ISS | |
| `page.fill("#aliquotaIss", ...)` | alíquota (se editável) | |
| `page.click(f"text={REGIME_APURACAO_TRIBUTOS.upper()}")` | regime tributário | |
| `page.select_option("#situacaoPisCofins", "00")` | situação PIS/COFINS | |

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

Bloco 1 de perguntas já foi respondido por texto (endereço automático,
certificado sem senha) — o que resta é mais rápido ver acontecendo do que
perguntar por WhatsApp:

- Os rascunhos parados no portal (pergunta 14 do Bloco 2) — quantos tem
  agora, o que a analista faz com eles.
- "Valor aproximado dos tributos" (pergunta 16) — muda de nota para nota?
- O grupo das ~50 empresas com antecedência de 10-12 dias — se a coluna
  nova já estiver na planilha nesse momento, conferir o nome/formato dela.

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
