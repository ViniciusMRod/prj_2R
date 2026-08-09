#!/usr/bin/env python3
"""
Esqueleto do robô de emissão de NFS-e (RPA) — Fase 2 do projeto de
automação para o cliente 2R.

ESTADO: ESQUELETO NÃO EXECUTÁVEL. As constantes do emitente e do serviço
abaixo já são dados REAIS, extraídos dos PDFs de notas emitidas que o 2R
enviou (DANFSe v1.0, Prefeitura Municipal de São Luís), e a regra de
cálculo do ISS retido está confirmada contra uma nota real. O que falta
é uma única coisa: uma sessão dentro da tela autenticada do portal.

NÃO EXECUTAR contra o portal de produção antes de:

  1. A Fase 1 estar concluída — `validar_planilha.py` rodando sem ERROS
     sobre a planilha do mês. Hoje ele ainda acusa erros bloqueantes de
     cadastro (documento truncado, tomador igual ao prestador).
  2. Confirmar os seletores reais de cada campo do formulário. Os
     seletores abaixo continuam sendo PLACEHOLDERS derivados do passo a
     passo textual do cliente — NÃO foram verificados contra o DOM da
     tela autenticada. Os PDFs confirmaram os VALORES a preencher, não
     os CAMPOS onde preenchê-los. Exige acesso à tela autenticada
     (sessão presencial na máquina do 2R, ou acesso de desenvolvimento
     temporário) para capturar via DevTools.
  3. CONFIRMAR AO VIVO o login com certificado — CONFIRMADO pela analista
     (2R, 31/07): o certificado A1 está instalado só no notebook DELA,
     não pede mais senha/PIN a cada acesso, e só ela emite hoje (um único
     operador, uma única máquina). Rodando o Chromium em modo visível
     (headless=False) NESSE NOTEBOOK, o Windows deve abrir o certificado
     automaticamente (ou o seletor nativo, se houver mais de um instalado)
     — o `input()` em `emitir_lote` já foi desenhado para esse passo
     manual, sem nenhuma config de `client_certificates` no Playwright.
     Ainda não OBSERVADO acontecendo — sem senha, é ainda mais provável
     que funcione de primeira, mas continua sendo o primeiro teste do
     spike. Consequência: este robô só pode rodar NESSE NOTEBOOK
     específico, nunca em servidor, nuvem ou máquina do consultor. Este
     código nunca lê nem copia o .pfx.

Os itens 2 e 3 se resolvem na MESMA sessão (ver ROTEIRO-SPIKE.md).

CONFIRMADO (2R, 31/07): o portal preenche o endereço do tomador sozinho
a partir do CNPJ/CPF — não é preciso digitar CEP nem coletar endereço
das 274 empresas. `preencher_nota` não precisa (e não deve) mexer em
campos de endereço.

O fluxo respeita o requisito de "semi-automatizado": o robô preenche o
formulário e PARA — o clique final em "Emitir" é sempre humano.
"""
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import openpyxl
from playwright.sync_api import Page, sync_playwright

# Toda a lógica de leitura/validação da planilha vem da Fase 1 — dígitos
# verificadores de CNPJ/CPF, detecção do cabeçalho, conversão numérica e
# detecção de descrição com competência vazia. Nada disso é reimplementado
# aqui: uma segunda cópia divergiria da primeira no primeiro ajuste.
from validar_planilha import (
    ALIQUOTA_ISS_MAXIMA,
    CNPJ_PRESTADOR,
    VALORES_NAO,
    classificar_documento,
    converte_numero,
    descricao_com_competencia_vazia,
    detectar_cabecalho,
    mapa_celulas_mescladas,
    mesmo_titular,
    texto_limpo,
    valores_com_merge,
)

LOGIN_URL = "https://www.nfse.gov.br/EmissorNacional/Login?ReturnUrl=%2fEmissorNacional%2f"

# ---------------------------------------------------------------------------
# EMITENTE (prestador) e SERVIÇO — dados do cliente, fora do versionamento.
# ---------------------------------------------------------------------------
# Tudo que identifica o prestador vive em `dados_cliente.py`, que o git
# ignora: o repositório é público e CNPJ, razão social, endereço, telefone
# e e-mail são dados de um terceiro real. Ver `dados_cliente.example.py`.
#
# CNPJ_PRESTADOR vem via validar_planilha (import acima) para haver uma
# única fonte da verdade — o validador também precisa dele para barrar
# tomador igual ao prestador.
from dados_cliente import (  # noqa: E402  (depois do try/except de validar_planilha)
    CODIGO_TRIBUTACAO_NACIONAL,
    DESCRICAO_SERVICO_PADRAO,
    EMAIL_PRESTADOR,
    INSCRICAO_MUNICIPAL_PRESTADOR,
    MUNICIPIO_PRESTADOR,
    NBS_CODIGO,
    RAZAO_SOCIAL_PRESTADOR,
    SERIE_DPS,
    TELEFONE_PRESTADOR,
    TOTAL_PARCELAS_CONTRATO,
    UF_PRESTADOR,
)

# Enquadramento tributário do emitente — texto exato impresso no DANFSe.
SIMPLES_NACIONAL_SITUACAO = "Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)"
REGIME_APURACAO_TRIBUTOS = (
    "Regime de apuração dos tributos federais e municipal pelo Simples Nacional"
)

# ---------------------------------------------------------------------------
# SERVIÇO — fixo em todas as notas. CODIGO_TRIBUTACAO_NACIONAL, NBS_CODIGO
# e DESCRICAO_SERVICO_PADRAO vêm de dados_cliente (import acima).
# ---------------------------------------------------------------------------
CODIGO_TRIBUTACAO_NACIONAL_DESCRICAO = (
    "Assessoria ou consultoria de qualquer natureza, não contida em outros itens"
)

# Rótulo do item NBS como aparece na LISTA do portal. Veio do passo a passo
# textual do cliente, NÃO do PDF — o PDF só confirma o código numérico.
# TODO: confirmar o rótulo exato na tela antes de usá-lo como seletor.
NBS_ITEM_ROTULO = (
    "SERVIÇOS DE CONSULTORIA TÉCNICA E CIENTIFICA, NÃO CLASSIFICADOS EM SUBPOSIÇÕES ANTERIORES"
)

# Município de prestação do serviço (igual ao do prestador nos dois PDFs).
MUNICIPIO_PRESTACAO = f"{MUNICIPIO_PRESTADOR}-{UF_PRESTADOR}"

# Tributação do ISSQN: idêntica nas duas notas, INCLUSIVE na que tem
# retenção. O que muda no caso com retenção é só a retenção/alíquota.
TRIBUTACAO_ISSQN = "Operação Tributável"
REGIME_ESPECIAL_TRIBUTACAO = "Nenhum"
SUSPENSAO_EXIGIBILIDADE = "Não"

# DESCRICAO_SERVICO_PADRAO vem de dados_cliente (import acima). É usada em
# todas as notas, exceto nas 3 empresas que têm descrição própria na
# planilha (ver DESCRICAO_MARCADOR_PENDENTE).

# Marcador presente na descrição de 3 empresas da planilha:
# "COMPETÊNCIA:\nNFS-E REFERENTE AOS SERVIÇOS REALIZADOS NO MÊS ANTERIOR".
# O que vem depois de "COMPETÊNCIA:" está VAZIO na planilha.
#
# TODO (CONFIRMAR COM O 2R): a hipótese é que o operador digite o mês/ano
# de competência manualmente a cada emissão. NÃO CONFIRMADO. Enquanto não
# houver confirmação, o robô se RECUSA a emitir essas notas (levanta
# DescricaoNaoResolvidaError, ver conferir_descricoes_pendentes) em vez de
# mandar a descrição incompleta para o portal.
DESCRICAO_MARCADOR_PENDENTE = "COMPETÊNCIA:"

# Total de parcelas do contrato, conforme o nome dos PDFs que o 2R já
# salva hoje ("... 07 DE 12").
TOTAL_PARCELAS_CONTRATO = 12

# Nomes de arquivo reservados no Windows.
_NOMES_RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {
    f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)
}
_CARACTERES_INVALIDOS_WINDOWS = r'[<>:"/\\|?*\x00-\x1f]'


class PlanilhaInvalidaError(RuntimeError):
    """A planilha não vira lista de notas sem intervenção humana."""


class DescricaoNaoResolvidaError(RuntimeError):
    """Descrição com marcador pendente (ex.: 'COMPETÊNCIA:' sem valor)."""


@dataclass
class NotaFiscal:
    """Uma nota a emitir. Espelha uma linha da planilha do 2R.

    `aliquota_iss` guarda a ALÍQUOTA e não um booleano de propósito: o
    portal calcula a Base de Cálculo do ISSQN e o ISSQN Apurado a partir
    dela, e o DANFSe imprime os dois. `None` = sem retenção (271 das 274
    linhas da planilha atual).

    TODO (CONFIRMAR COM O 2R): hoje a alíquota é lida da linha do TOMADOR,
    mas as 3 linhas com retenção têm o mesmo 0.0419 para tomadores sem
    relação entre si — indício forte de que 4,19% é a alíquota efetiva de
    ISS do PRESTADOR no Simples Nacional, que muda de competência para
    competência conforme o RBT12. Se for isso, a alíquota é um parâmetro
    MENSAL do lote, não um atributo de cadastro, e a planilha ficaria
    desatualizada em silêncio quando a faixa mudar.
    """

    empresa: str
    # Só dígitos. CNPJ (14) ou CPF (11) — o 2R emite para PF em 6 casos.
    documento_tomador: str
    valor: float
    # A coluna VENC é o DIA do mês (1..31), não uma data. Não entra na
    # NFS-e; serve para ordenar/agendar o lote.
    #
    # CONFIRMADO (2R, 31/07): a analista roda ~8 lotes/mês, cada um
    # emitindo quem vence nos "próximos dias". A antecedência padrão é de
    # 3 a 5 dias — MAS ~50 empresas (nota precisa ir junto com o boleto)
    # exigem 10 a 12 dias de antecedência. O 2R vai sinalizar essas ~50
    # na própria planilha (não numa aba separada) — TODO: mapear a coluna
    # assim que ela existir. Até lá, o agrupador de lote por vencimento
    # (ainda não escrito — ver README) não pode assumir uma janela única
    # para todas as empresas.
    dia_vencimento: int | None = None
    # None = sem retenção. Ex.: 0.0419 nas 3 empresas com ISS de 4,19%.
    aliquota_iss: float | None = None
    # None/vazio = usa DESCRICAO_SERVICO_PADRAO.
    descricao: str | None = None
    # Linha de origem na planilha, para mensagens rastreáveis.
    linha_planilha: int | None = None

    @property
    def tem_retencao_iss(self) -> bool:
        return self.aliquota_iss is not None

    @property
    def tipo_documento(self) -> str:
        return {14: "CNPJ", 11: "CPF"}.get(len(self.documento_tomador), "DOCUMENTO INVÁLIDO")

    @property
    def descricao_pendente(self) -> bool:
        """True se a descrição própria ainda tiver competência em branco."""
        return bool(self.descricao) and descricao_com_competencia_vazia(self.descricao)

    def descricao_efetiva(self) -> str:
        """Descrição a enviar ao portal.

        Levanta DescricaoNaoResolvidaError se a descrição tiver marcador
        pendente: é melhor falhar alto do que emitir uma nota com o campo
        de competência em branco.
        """
        if not self.descricao or not self.descricao.strip():
            return DESCRICAO_SERVICO_PADRAO
        if self.descricao_pendente:
            raise DescricaoNaoResolvidaError(
                f"L{self.linha_planilha} ({self.empresa}): descrição com "
                f"'{DESCRICAO_MARCADOR_PENDENTE}' sem valor. Preencher a competência "
                "(mês/ano) antes de emitir — ver TODO em DESCRICAO_MARCADOR_PENDENTE."
            )
        return self.descricao.strip()


def calcular_iss(valor: float, aliquota: float) -> tuple[float, float]:
    """Calcula ISSQN apurado e valor líquido de uma nota com retenção.

    Regra CONFIRMADA pelo DANFSe da nota do CONSELHO DE ARQUITETURA E
    URBANISMO DO MARANHÃO (NF 547):

        BC ISSQN      = Valor do Serviço
        ISSQN Apurado = Valor do Serviço × Alíquota  (2 casas, meio p/ cima)
        Valor Líquido = Valor do Serviço − ISSQN Retido

    Caso real: 243,00 × 4,19% = 10,1817 → 10,18; líquido 232,82.

    A alíquota é informada em FRAÇÃO (0.0419 = 4,19%), como está na
    planilha. Valores acima de 1 são rejeitados para pegar o erro clássico
    de passar 4.19 no lugar de 0.0419 — que calcularia ISS 100x maior.
    O teto de plausibilidade do ISS (ALIQUOTA_ISS_MAXIMA, 5%) é cobrado
    na leitura da planilha, não aqui: esta função é só a aritmética.

    Usa Decimal com ROUND_HALF_UP porque o round() do Python arredonda o
    meio para o par e ainda opera sobre float binário: por exemplo,
    round(102.50 * 0.05, 2) devolve 5.12, quando o esperado é 5.13.
    Valor de imposto não pode depender desse detalhe.

    Retorna (issqn_apurado, valor_liquido).
    """
    if valor is None or valor <= 0:
        raise ValueError(f"Valor do serviço inválido para cálculo de ISS: {valor!r}")
    if aliquota is None or aliquota <= 0 or aliquota > 1:
        raise ValueError(
            f"Alíquota de ISS inválida: {aliquota!r}. Informe a fração (0.0419 = 4,19%)."
        )

    centavos = Decimal("0.01")
    valor_dec = Decimal(str(valor)).quantize(centavos, rounding=ROUND_HALF_UP)
    issqn = (valor_dec * Decimal(str(aliquota))).quantize(centavos, rounding=ROUND_HALF_UP)
    liquido = (valor_dec - issqn).quantize(centavos, rounding=ROUND_HALF_UP)
    return float(issqn), float(liquido)


def carregar_notas(caminho: Path) -> list[NotaFiscal]:
    """Lê a planilha de controle e devolve a lista de notas a emitir.

    Reusa `detectar_cabecalho` do validador, então funciona tanto no
    schema novo (linha 1 = título, linha 2 = cabeçalho) quanto no antigo.

    Falha alto — listando TODAS as linhas problemáticas de uma vez — em
    vez de emitir nota errada silenciosamente. Bloqueia o que tornaria a
    NOTA errada:
      - documento ausente, truncado ou com DV inválido;
      - tomador com o CNPJ do próprio prestador (erro de cadastro real,
        erro de cadastro real, já encontrado numa linha da planilha);
      - valor ausente, não numérico ou não positivo;
      - retenção de ISS incoerente com a coluna de alíquota;
      - alíquota fora do intervalo plausível (provável erro de escala);
      - mesmo documento em cadastros de titulares diferentes (checagem
        CRUZADA entre linhas — caso real de duas empresas distintas com o
        mesmo CNPJ, que as validações linha a linha não pegam);
      - coluna esperada ausente do cabeçalho: sem a coluna, a regra que
        depende dela seria pulada em silêncio (perder as duas colunas de
        ISS emitiria as 3 notas com retenção como se não tivessem).

    NÃO bloqueia vencimento ausente: o dia de vencimento não entra na
    NFS-e, só serve para organizar o lote. Para o validador da Fase 1
    isso é ERRO (impede agendar), e é lá que deve ser resolvido.

    NÃO bloqueia descrição com competência pendente na LEITURA — isso é
    conferido em conferir_descricoes_pendentes(), imediatamente antes da
    emissão, porque o operador pode resolver a competência sem mexer na
    planilha.
    """
    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb.active

    linha_cabecalho, cabecalho, colunas = detectar_cabecalho(ws)
    if not colunas:
        raise PlanilhaInvalidaError(
            f"Não foi possível localizar a linha de cabeçalho em '{caminho.name}'."
        )

    # "descricao", "retencao_iss" e "aliquota_iss" são obrigatórias aqui de
    # propósito: se o cabeçalho for reformatado e elas deixarem de casar, o
    # robô emitiria as notas com retenção como isentas e com a descrição
    # padrão no lugar da específica, sem nenhum sinal de erro.
    faltando = [
        c for c in ("empresa", "documento", "valor", "descricao", "retencao_iss", "aliquota_iss")
        if c not in colunas
    ]
    if faltando:
        raise PlanilhaInvalidaError(
            f"Planilha sem colunas obrigatórias para emitir: {faltando}. "
            f"Cabeçalho detectado na linha {linha_cabecalho}: {cabecalho}"
        )

    mescladas = mapa_celulas_mescladas(ws)
    notas: list[NotaFiscal] = []
    problemas: list[str] = []

    for linha in ws.iter_rows(min_row=linha_cabecalho + 1):
        valores, _herdados = valores_com_merge(linha, mescladas)
        if all(str(v).strip() == "" for v in valores if v is not None) and not any(
            isinstance(v, (int, float)) for v in valores
        ):
            continue

        num_linha = linha[0].row

        def celula(chave, _valores=valores):
            indice = colunas.get(chave)
            if indice is None or indice >= len(_valores):
                return None
            return _valores[indice]

        empresa_bruta = celula("empresa")
        empresa = str(empresa_bruta).strip() if empresa_bruta is not None else ""
        if not empresa:
            # Descartar em silêncio deixaria a empresa sem nota no mês sem
            # ninguém perceber: linha com dados e sem nome é problema.
            problemas.append(
                f"L{num_linha}: linha com dados mas sem nome da empresa — "
                "impossível saber para quem emitir"
            )
            continue

        # ---------- Documento (CNPJ ou CPF) ----------
        tipo_doc, digitos, erro_doc = classificar_documento(celula("documento"))
        if erro_doc:
            problemas.append(f"L{num_linha} ({empresa}): {erro_doc}")
            continue
        if digitos == CNPJ_PRESTADOR:
            problemas.append(
                f"L{num_linha} ({empresa}): tomador é o CNPJ do PRÓPRIO PRESTADOR "
                f"({CNPJ_PRESTADOR}) — a nota sairia para a própria empresa"
            )
            continue

        # ---------- Valor ----------
        valor = converte_numero(celula("valor"))
        if valor is None or valor <= 0:
            problemas.append(
                f"L{num_linha} ({empresa}): VALOR '{celula('valor')}' ausente, "
                "não numérico ou não positivo"
            )
            continue

        # ---------- Retenção de ISS ----------
        retencao_bruta = celula("retencao_iss")
        aliquota_bruta = celula("aliquota_iss")
        retencao_txt = texto_limpo(retencao_bruta)
        tem_marca_retencao = bool(retencao_txt) and retencao_txt not in VALORES_NAO
        aliquota_preenchida = aliquota_bruta not in (None, "")
        aliquota = converte_numero(aliquota_bruta)

        if tem_marca_retencao and not aliquota_preenchida:
            problemas.append(
                f"L{num_linha} ({empresa}): retenção de ISS marcada como "
                f"'{str(retencao_bruta).strip()}' mas sem alíquota"
            )
            continue
        if aliquota_preenchida and not tem_marca_retencao:
            problemas.append(
                f"L{num_linha} ({empresa}): alíquota '{aliquota_bruta}' preenchida "
                "sem a retenção marcada como SIM — colunas incoerentes"
            )
            continue
        if aliquota_preenchida:
            if aliquota is None or aliquota <= 0:
                problemas.append(
                    f"L{num_linha} ({empresa}): alíquota '{aliquota_bruta}' não é "
                    "um número positivo"
                )
                continue
            if aliquota > ALIQUOTA_ISS_MAXIMA:
                # Não "corrigimos" dividindo por 100: 4.19 em vez de 0.0419 é
                # erro de cadastro e tem que voltar para o 2R corrigir.
                problemas.append(
                    f"L{num_linha} ({empresa}): alíquota {aliquota} acima do teto "
                    f"plausível de ISS ({ALIQUOTA_ISS_MAXIMA:.0%}) — provável erro de "
                    f"escala (o esperado seria {aliquota / 100:.4f})"
                )
                continue
        else:
            aliquota = None

        # ---------- Vencimento (dia do mês) ----------
        dia = converte_numero(celula("vencimento"))
        dia_vencimento = int(dia) if dia is not None and 1 <= dia <= 31 else None

        # ---------- Descrição ----------
        descricao_bruta = celula("descricao")
        descricao = str(descricao_bruta) if descricao_bruta not in (None, "") else None

        notas.append(
            NotaFiscal(
                empresa=empresa,
                documento_tomador=digitos,
                valor=valor,
                dia_vencimento=dia_vencimento,
                aliquota_iss=aliquota,
                descricao=descricao,
                linha_planilha=num_linha,
            )
        )

    # ---------- Checagem CRUZADA: mesmo documento em titulares diferentes ----------
    # Validação linha a linha não pega isto. É o caso real de L105/L106
    # (duas empresas distintas com o mesmo CNPJ, por arrasto de célula no
    # Excel): uma das duas notas sairia para o tomador errado.
    por_documento = defaultdict(list)
    for nota in notas:
        por_documento[nota.documento_tomador].append(nota)
    for documento, repetidas in sorted(por_documento.items()):
        if len(repetidas) < 2:
            continue
        onde = ", ".join(f"L{n.linha_planilha} ({n.empresa})" for n in repetidas)
        if mesmo_titular([n.empresa for n in repetidas]):
            # Mesmo titular com vários contratos (caso real: uma pessoa
            # física com duas fazendas, duas notas separadas). Não bloqueia.
            continue
        problemas.append(
            f"documento {documento} repetido em cadastros de titulares diferentes: "
            f"{onde} — uma das notas sairia para o tomador errado"
        )

    if problemas:
        raise PlanilhaInvalidaError(
            f"{len(problemas)} problema(s) impedem a emissão:\n  - " + "\n  - ".join(problemas)
        )

    return notas


def conferir_descricoes_pendentes(notas: list[NotaFiscal]) -> None:
    """Aborta o lote inteiro se alguma descrição tiver competência vazia.

    Roda ANTES de abrir o navegador: falha alto e cedo, sem emitir nada.
    São as 3 empresas cuja descrição própria tem "COMPETÊNCIA:" em branco.
    Enquanto o cliente não confirmar como esse campo é preenchido, o lote
    não roda com elas dentro.
    """
    pendentes = [n for n in notas if n.descricao_pendente]
    if not pendentes:
        return
    detalhe = "\n  - ".join(f"L{n.linha_planilha} ({n.empresa})" for n in pendentes)
    raise DescricaoNaoResolvidaError(
        f"{len(pendentes)} nota(s) com '{DESCRICAO_MARCADOR_PENDENTE}' sem valor na "
        f"descrição:\n  - {detalhe}\n"
        "Preencha a competência (mês/ano) dessas descrições ou remova essas notas do "
        "lote. Nada foi emitido."
    )


def _sanitizar_nome_arquivo(nome: str) -> str:
    """Deixa o nome válido no Windows, preservando a legibilidade."""
    # Caractere de controle vira ESPAÇO, não some: há nomes na planilha com
    # Alt+Enter no meio ("...ODONTOLOGIA E ESTETICA\nDO MARANHAO LTDA") e
    # removê-lo colaria as palavras ("ESTETICADO").
    limpo = re.sub(_CARACTERES_INVALIDOS_WINDOWS, " ", nome or "")
    limpo = re.sub(r"\s+", " ", limpo).strip()
    limpo = limpo.rstrip(". ")
    if limpo.upper() in _NOMES_RESERVADOS_WINDOWS:
        limpo = f"_{limpo}"
    if not limpo:
        limpo = "SEM NOME"
    return limpo[:150]


def montar_nome_pdf(
    nota: NotaFiscal, indice_mes: int, total_parcelas: int = TOTAL_PARCELAS_CONTRATO
) -> str:
    """Nome do PDF no mesmo padrão que o 2R já usa hoje.

    Padrão observado nos arquivos do cliente:
        "NF MES 07 D M FERREIRA PANIFICACAO 07 DE 12.pdf"
    (um dos arquivos reais veio com espaço duplo depois de "NF" —
    inconsistência de digitação humana; aqui o espaçamento é sempre
    normalizado e o nome da empresa é sanitizado para o Windows.)

    TODO (CONFIRMAR COM O 2R): `indice_mes` é o mês do CALENDÁRIO ou a
    PARCELA do contrato? A evidência é contraditória: a nota rotulada
    "MES 08" (CAU-MA, NF 547) tem competência 23/07/2026 e foi emitida
    ANTES da rotulada "MES 07" (NF 563, competência 24/07/2026) — as duas
    na competência de julho. Se for parcela de contrato, o número precisa
    vir de um controle por empresa, não do calendário, e cada empresa
    terá o seu. Até a confirmação, o mesmo número é repetido nas duas
    posições, como nos arquivos reais.
    """
    if not 1 <= indice_mes <= total_parcelas:
        raise ValueError(f"indice_mes fora do intervalo 1..{total_parcelas}: {indice_mes}")
    empresa = _sanitizar_nome_arquivo(nota.empresa)
    return f"NF MES {indice_mes:02d} {empresa} {indice_mes:02d} DE {total_parcelas}.pdf"


def preencher_nota(page: Page, nota: NotaFiscal) -> None:
    """Preenche o formulário até a tela de revisão. NUNCA clica em emitir."""
    if nota.documento_tomador == CNPJ_PRESTADOR:
        raise ValueError(
            f"Tomador é o próprio prestador ({CNPJ_PRESTADOR}) em L{nota.linha_planilha} "
            f"({nota.empresa}) — emissão bloqueada."
        )

    # Falha antes de tocar no formulário se a descrição tiver pendência.
    descricao = nota.descricao_efetiva()

    if nota.aliquota_iss is not None and nota.aliquota_iss > ALIQUOTA_ISS_MAXIMA:
        raise ValueError(
            f"Alíquota {nota.aliquota_iss} acima do teto plausível de ISS "
            f"({ALIQUOTA_ISS_MAXIMA:.0%}) em L{nota.linha_planilha} ({nota.empresa})."
        )

    # TODO: TODOS os seletores abaixo continuam PLACEHOLDERS (ids tipo
    # #documentoTomador nunca foram vistos no DOM real). Só os NOMES e a
    # ORDEM dos campos estão confirmados agora, via dois vídeos que o
    # cliente enviou (07-08/08) mostrando o preenchimento real na tela —
    # ver quadro completo em ROTEIRO-SPIKE.md. Falta ainda: abrir o DevTools
    # e pegar o seletor de cada um.
    #
    # Fluxo real tem MAIS telas que o mapeado antes por texto/PDF:
    #   Pessoas -> Serviço -> Tributação -> Valores -> Emitir NFS-e
    # (o portal chama de "Tributação" o que documentamos como "Serviço" +
    # "retenção" juntos — são passos separados na tela).
    #
    # CONFIRMADO (vídeo): valor e alíquota usam VÍRGULA decimal na tela
    # ("1.595,00", "4,19"), não ponto. Corrigido abaixo.
    #
    # TODO (CONFERÊNCIA MAIS VALIOSA QUE FALTA): depois de preencher o
    # documento, o portal resolve e exibe a RAZÃO SOCIAL do tomador. Reler
    # esse texto e comparar com nota.empresa, abortando em divergência, é a
    # única checagem que fecha a classe "CNPJ com dígito verificador válido
    # mas de outra empresa" — que nenhuma validação offline detecta.
    page.click("text=Emissão Completa")
    page.fill("#documentoTomador", nota.documento_tomador)  # "CPF/CNPJ *"

    # CONFIRMADO (vídeo): aba Serviço tem uma pergunta ANTES do código de
    # tributação, não documentada antes: "O serviço prestado é um caso de:
    # imunidade, exportação de serviço ou não incidência do ISSQN?" — as
    # 274 empresas da planilha são todas "Não" (nenhuma isenção conhecida).
    page.click("#casoImunidadeExportacao_nao")
    page.click(f"text={CODIGO_TRIBUTACAO_NACIONAL}")
    page.fill("#descricaoServico", descricao)  # "Descrição do Serviço *"
    page.click(f"text={NBS_ITEM_ROTULO}")

    def _valor_br(valor: float) -> str:
        """Formata valor no padrão que o campo do portal usa: vírgula."""
        return str(Decimal(str(valor)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)).replace(".", ",")

    # "Valor do serviço prestado *", na aba Valores.
    page.fill("#valorNota", _valor_br(nota.valor))

    if nota.tem_retencao_iss:
        # Confirmado pelo DANFSe da NF 547 e pelo vídeo do exemplo real
        # com retenção: BC ISSQN = valor do serviço, Alíquota Aplicada =
        # alíquota informada, ISSQN Apurado = valor × alíquota.
        issqn, liquido = calcular_iss(nota.valor, nota.aliquota_iss)
        page.click("#retencaoIssSim")
        # CONFIRMADO (vídeo): depois de marcar retenção, o portal pergunta
        # "Informe abaixo por quem o imposto será retido" — Retido pelo
        # Tomador / Retido pelo Intermediário. Sempre pelo Tomador aqui:
        # nenhuma nota do cliente tem intermediário.
        page.click("#retidoPeloTomador")
        # CONFIRMADO: alíquota É digitável (não vem do cadastro do
        # tomador). O próprio portal avisa: "Para o prestador de serviço
        # ME/EPP com apuração do ISSQN pelo simples nacional, é obrigatório
        # informar alíquota... é permitido informar alíquota mínima de
        # 1,8%" — mesmo piso usado em ALIQUOTA_ISS_MINIMA_PLAUSIVEL.
        page.fill("#aliquotaIss", f"{nota.aliquota_iss * 100:.2f}".replace(".", ","))
        # CONFIRMADO (vídeo): duas perguntas Sim/Não aparecem em seguida,
        # sempre "Não" nas notas já vistas — nenhuma tem benefício
        # municipal nem dedução/redução conhecidos.
        page.click("#beneficioMunicipal_nao")
        page.click("#deducaoReducao_nao")
        print(
            f"  [conferir na tela] BC ISSQN R$ {nota.valor:.2f} | alíquota "
            f"{nota.aliquota_iss * 100:.2f}% | ISSQN apurado R$ {issqn:.2f} | "
            f"líquido R$ {liquido:.2f}"
        )
    else:
        page.click("#retencaoIssNao")

    page.click(f"text={REGIME_APURACAO_TRIBUTOS.upper()}")
    page.select_option("#situacaoPisCofins", "00")
    # CONFIRMADO (vídeo): campo separado, sempre visto como "PIS/COFINS/CSLL
    # Não Retidos" — não documentado antes.
    page.select_option("#tipoRetencaoPisCofinsCsll", "NAO_RETIDOS")
    # TODO: "VALOR APROXIMADO DOS TRIBUTOS" (Federal/Estadual/Municipal %)
    # apareceu no vídeo já preenchido com 0,90/0,10/0,00 — parece ser
    # CONFIGURAÇÃO DA CONTA do emitente, não campo por nota. Confirmar no
    # spike se essa tela aparece a cada nota ou só na primeira vez.
    # Formulário preenchido — PARA AQUI. A emissão é um clique humano.


def _chave_registro(nota: NotaFiscal) -> str:
    """Identidade da nota no registro de emissão: documento + empresa.

    NÃO usa `linha_planilha`. O cadastro do 2R muda todo mês — já foi de
    165 para 274 empresas e vai continuar. Se a chave fosse o número da
    linha, inserir uma empresa no meio da planilha deslocaria a linha de
    TODAS as empresas abaixo dela, e retomar um lote interrompido
    (Ctrl+C no meio de 274 notas, planilha editada nesse intervalo)
    casaria o registro com a empresa errada — pulando uma nota que ainda
    não saiu, ou reemitindo uma que já saiu.

    Documento + empresa é estável mesmo com a lista mudando de tamanho.
    Precisa dos DOIS (não só o documento) porque há caso real de um mesmo
    CPF em duas notas legítimas (pessoa física com dois estabelecimentos)
    — ver `mesmo_titular` em validar_planilha.
    """
    return f"{nota.documento_tomador}|{nota.empresa}"


def caminho_registro(pasta_saida: Path, indice_mes: int) -> Path:
    """Arquivo de controle das notas já emitidas neste lote."""
    return pasta_saida / f"emitidas_{indice_mes:02d}.json"


def carregar_registro(caminho: Path) -> dict:
    """Lê o registro de emissão; devolve {} se ainda não existir."""
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise RuntimeError(
            f"Registro de emissão '{caminho}' ilegível ({erro}). Conferir manualmente "
            "quais notas já saíram ANTES de rodar o lote de novo — sem isso há risco "
            "de emitir nota duplicada."
        ) from erro


def registrar_emitida(caminho: Path, registro: dict, nota: NotaFiscal) -> None:
    """Grava a nota como emitida, imediatamente (sobrevive a Ctrl+C)."""
    registro[_chave_registro(nota)] = {
        "linha_planilha": nota.linha_planilha,  # só para rastreio humano
        "empresa": nota.empresa,
        "documento": nota.documento_tomador,
        "valor": nota.valor,
        "confirmada_em": datetime.now().isoformat(timespec="seconds"),
    }
    caminho.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")


def emitir_lote(notas: list[NotaFiscal], pasta_saida: Path, indice_mes: int) -> None:
    """Percorre o lote preenchendo cada nota e parando para revisão humana.

    O robô NUNCA clica em "Emitir": quem confirma na tela é o operador do
    2R. O Enter no terminal apenas libera a próxima nota.

    Mantém um REGISTRO das notas já confirmadas (um JSON por lote, gravado a
    cada nota) e pula as que já saíram ao ser reexecutado. Sem isso, retomar
    um lote interrompido — cenário previsto, já que o operador pode dar
    Ctrl+C no meio de 274 notas — reemitiria tudo desde a primeira. NFS-e
    duplicada não se desfaz com um clique: cancelamento tem prazo e a nota
    já compôs a receita da competência.
    """
    # Erros de parâmetro precisam estourar ANTES de abrir o navegador e
    # preencher a primeira nota — não com o formulário já na tela.
    if not 1 <= indice_mes <= TOTAL_PARCELAS_CONTRATO:
        raise ValueError(
            f"indice_mes fora do intervalo 1..{TOTAL_PARCELAS_CONTRATO}: {indice_mes}"
        )
    if not notas:
        raise ValueError("Lote vazio: nada a emitir.")

    # Falha antes de abrir o navegador se houver descrição não resolvida.
    conferir_descricoes_pendentes(notas)

    pasta_saida.mkdir(parents=True, exist_ok=True)
    registro_caminho = caminho_registro(pasta_saida, indice_mes)
    registro = carregar_registro(registro_caminho)

    pendentes = [n for n in notas if _chave_registro(n) not in registro]
    ja_emitidas = len(notas) - len(pendentes)

    # Conferência de totais antes de gerar documentos fiscais: um zero a mais
    # numa célula (475 -> 4750) passa por todas as validações de linha.
    total = sum(n.valor for n in pendentes)
    maior = max(pendentes, key=lambda n: n.valor)
    print(f"\nLote {indice_mes:02d} de {TOTAL_PARCELAS_CONTRATO}")
    print(f"  Notas a emitir:   {len(pendentes)}" +
          (f"  ({ja_emitidas} já emitidas serão puladas)" if ja_emitidas else ""))
    print(f"  Soma dos valores: R$ {total:,.2f}".replace(",", "#").replace(".", ",")
          .replace("#", "."))
    print(f"  Maior nota:       R$ {maior.valor:,.2f} — L{maior.linha_planilha} {maior.empresa}"
          .replace(",", "#").replace(".", ",").replace("#", "."))
    print(f"  Com retenção ISS: {sum(1 for n in pendentes if n.tem_retencao_iss)}")
    print(f"  Registro do lote: {registro_caminho}")
    if input("\nConfere? Digite SIM para abrir o navegador: ").strip().upper() != "SIM":
        print("Cancelado. Nada foi emitido.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL)

        input("Faça o login manual com o certificado digital e pressione Enter para continuar...")

        for posicao, nota in enumerate(pendentes, start=1):
            preencher_nota(page, nota)
            nome_pdf = montar_nome_pdf(nota, indice_mes)
            input(
                f"[{posicao}/{len(pendentes)}] L{nota.linha_planilha} {nota.empresa} "
                f"({nota.tipo_documento} {nota.documento_tomador}, R$ {nota.valor:.2f}) "
                "preenchida. REVISE e clique em 'Emitir' na tela. Depois clique em 'Baixar "
                "DANFSe', resolva o desafio 'Sou humano' que o portal pedir e salve o PDF "
                f"como '{nome_pdf}'. Enter DEPOIS de emitir e baixar (marca como emitida), "
                "Ctrl+C para interromper o lote..."
            )
            # O Enter acima é a confirmação humana de que a nota SAIU. Grava
            # já, para que uma interrupção logo em seguida não a reemita.
            registrar_emitida(registro_caminho, registro, nota)
            # NÃO AUTOMATIZÁVEL (confirmado por vídeo, 07/08): a tela pós-
            # emissão tem os botões "Baixar XML" / "Baixar DANFSe" /
            # "Visualizar NFS-e" / "NFS-e emitidas" / "Nova NFS-e" — mas
            # clicar em baixar abre um modal "VALIDAÇÃO DE USUÁRIO" com
            # hCaptcha ("Sou humano" + desafio de imagem tipo "selecione os
            # animais que nascem de ovos"). Resolver captcha
            # automaticamente está fora de questão (viola os termos do
            # hCaptcha/portal e não é o tipo de automação deste projeto).
            # O download PRECISA do clique humano acima — não dá para
            # substituir por page.expect_download() sozinho.

        browser.close()


if __name__ == "__main__":
    raise SystemExit(
        "Esqueleto ainda não pronto para execução — resolver os TODOs e a "
        "docstring do módulo antes de rodar contra o portal real."
    )
