#!/usr/bin/env python3
"""
Validador da planilha de controle de notas fiscais do 2R.

Confere, antes de qualquer automação de emissão (Fase 2), se a planilha
está pronta: documento (CNPJ ou CPF) válido e sem duplicidade indevida,
valor e vencimento preenchidos, e coerência das colunas de retenção de ISS.

Suporta os dois layouts já vistos no projeto:
  - Schema NOVO  (linha 1 = título, linha 2 = cabeçalho):
    EMPRESA / CNPJ / VALOR / VENC / DESCRIÇÃO DA NOTA / RETENÇÃO DE ISS? / VALOR ALIQUOTA ISS
  - Schema ANTIGO (linha 1 = cabeçalho):
    EMPRESA / VALOR / VENC. / ISS / ISS Valor / CNPJ:

A linha de cabeçalho é detectada automaticamente e as colunas são
mapeadas por NOME normalizado (a ordem mudou entre os dois layouts).

O cadastro de empresas MUDA todo mês (já foi de 165 para 274 — e vai
continuar entrando e saindo contrato). Isso não é erro, mas precisa
aparecer: a cada execução o validador compara a lista de empresas com o
snapshot da execução anterior (`estado/roster_empresas.json`, ignorado
pelo git) e avisa quem entrou e quem saiu, sem bloquear.

Uso:
    python validar_planilha.py caminho/da/planilha.xlsx [--saida caminho/erros.xlsx] [--roster caminho/roster.json]

Códigos de saída:
    0 = sem ERROS (pode haver AVISOS)
    1 = pelo menos um ERRO
"""
import argparse
import datetime
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

# CNPJ do prestador (a empresa emitente). Nenhum tomador pode ter este
# documento — a nota sairia para a própria empresa emitente.
#
# Vem de `dados_cliente.py`, que NÃO é versionado: o repositório é público
# e o CNPJ/razão social do prestador são dados de um terceiro real. Ver
# `dados_cliente.example.py` para o modelo.
try:
    from dados_cliente import CNPJ_PRESTADOR
except ImportError as erro:  # pragma: no cover - erro de instalação
    raise SystemExit(
        "Arquivo 'src/dados_cliente.py' não encontrado.\n"
        "Ele guarda os dados do prestador e não é versionado de propósito.\n"
        "Para criar:  cp src/dados_cliente.example.py src/dados_cliente.py\n"
        "e preencher com os dados reais (estão nos PDFs de notas já emitidas)."
    ) from erro

# Intervalo plausível para alíquota de ISS, expressa como fração decimal.
# O piso existe porque a alíquota efetiva de ISS no Simples Nacional não
# desce abaixo de ~2%: um dedo escorregado (0.0419 -> 0.0041) recolheria
# ISS 10x menor e passaria despercebido.
ALIQUOTA_ISS_MAXIMA = 0.05  # 5%
ALIQUOTA_ISS_MINIMA_PLAUSIVEL = 0.02  # 2%

# Quantas linhas do topo são inspecionadas à procura do cabeçalho.
MAX_LINHAS_BUSCA_CABECALHO = 10

SEVERIDADE_ERRO = "ERRO"
SEVERIDADE_AVISO = "AVISO"

COLUNAS_ESPERADAS = {
    "empresa": ["EMPRESA", "EMPRESA/CLIENTE", "CLIENTE", "TOMADOR"],
    "documento": ["CNPJ", "CPF", "CNPJ/CPF", "CPF/CNPJ", "DOCUMENTO"],
    "valor": ["VALOR", "VALOR DA NOTA", "VALOR NOTA"],
    "vencimento": ["VENC", "VENCIMENTO", "DIA VENC", "DIA DE VENCIMENTO"],
    "descricao": ["DESCRICAO DA NOTA", "DESCRICAO", "DESCRICAO DO SERVICO"],
    "retencao_iss": ["RETENCAO DE ISS", "RETENCAO ISS", "ISS", "RETEM ISS"],
    "aliquota_iss": ["VALOR ALIQUOTA ISS", "ALIQUOTA ISS", "ALIQUOTA DE ISS", "ISS VALOR"],
}

# Sufixos societários ignorados ao comparar nomes de empresa.
SUFIXOS_SOCIETARIOS = {
    "LTDA", "ME", "EPP", "SA", "EIRELI", "MEI", "CIA", "S", "A", "E",
    "MATRIZ", "FILIAL", "DE", "DA", "DO", "DAS", "DOS",
}

VALORES_SIM = {"SIM", "S", "X"}
VALORES_NAO = {"NAO", "N", "-", "0"}


def remove_acentos(texto: str) -> str:
    """Remove acentuação para comparações insensíveis a diacríticos."""
    normalizado = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def normaliza_cabecalho(valor) -> str:
    """Normaliza um rótulo de cabeçalho: strip + upper + remove pontuação final."""
    texto = remove_acentos(str(valor if valor is not None else "")).upper()
    texto = texto.replace("\n", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    # Remove pontuação sobrando no fim ("EMPRESA: ", "VENC.", "RETENÇÃO DE ISS? ")
    texto = re.sub(r"[\s:?.\-]+$", "", texto)
    return texto.strip()


def mapear_colunas(cabecalho) -> dict:
    """Mapeia chave lógica -> índice da coluna, por NOME normalizado."""
    mapa = {}
    normalizado = {}
    for indice, valor in enumerate(cabecalho):
        chave = normaliza_cabecalho(valor)
        if chave and chave not in normalizado:
            normalizado[chave] = indice
    for chave, alternativas in COLUNAS_ESPERADAS.items():
        for alt in alternativas:
            if alt in normalizado:
                mapa[chave] = normalizado[alt]
                break
    return mapa


def detectar_cabecalho(ws):
    """
    Procura a primeira linha do topo que se pareça com um cabeçalho.

    Necessário porque o schema novo tem uma linha de título antes do
    cabeçalho (linha 1 = título, linha 2 = cabeçalho) e o antigo não.
    Retorna (numero_da_linha, cabecalho, mapa_de_colunas).
    """
    limite = min(MAX_LINHAS_BUSCA_CABECALHO, ws.max_row or 1)
    for linha in ws.iter_rows(min_row=1, max_row=limite):
        cabecalho = [c.value for c in linha]
        mapa = mapear_colunas(cabecalho)
        # Um cabeçalho reconhecível precisa ter EMPRESA e pelo menos 3 colunas
        # conhecidas — evita casar com a linha de título ou com uma linha de dados.
        if "empresa" in mapa and len(mapa) >= 3:
            return linha[0].row, cabecalho, mapa
    return None, None, {}


def mapa_celulas_mescladas(ws) -> dict:
    """Mapeia (linha, coluna) -> valor da célula âncora de cada intervalo mesclado.

    O openpyxl devolve None para todas as células de um intervalo mesclado
    exceto a âncora (canto superior esquerdo). Sem este mapa, um merge como
    D20:D21 (usado na planilha real para repetir o dia de vencimento) faz o
    script ler "vazio" onde o operador vê o valor preenchido na tela.
    """
    mapa = {}
    for intervalo in ws.merged_cells.ranges:
        ancora = ws.cell(row=intervalo.min_row, column=intervalo.min_col).value
        if ancora is None:
            continue
        for num_linha in range(intervalo.min_row, intervalo.max_row + 1):
            for num_coluna in range(intervalo.min_col, intervalo.max_col + 1):
                if (num_linha, num_coluna) != (intervalo.min_row, intervalo.min_col):
                    mapa[(num_linha, num_coluna)] = ancora
    return mapa


def valores_com_merge(linha, mescladas: dict):
    """Valores de uma linha, preenchendo células vazias herdadas de merges.

    Retorna (valores, indices_herdados) — o segundo permite avisar o
    operador de que aquele dado não estava na própria célula.
    """
    valores = [c.value for c in linha]
    herdados = set()
    if not mescladas:
        return valores, herdados
    for posicao, celula in enumerate(linha):
        if valores[posicao] is None:
            herdado = mescladas.get((celula.row, celula.column))
            if herdado is not None:
                valores[posicao] = herdado
                herdados.add(posicao)
    return valores, herdados


def so_digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto if texto is not None else ""))


def dv_cnpj(base12: str) -> str:
    """Calcula os dois dígitos verificadores a partir dos 12 dígitos base."""

    def dv(nums, pesos):
        total = sum(int(n) * p for n, p in zip(nums, pesos))
        resto = total % 11
        return "0" if resto < 2 else str(11 - resto)

    d1 = dv(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = dv(base12 + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d1 + d2


def cnpj_valido(digitos: str) -> bool:
    """Valida os dois dígitos verificadores de um CNPJ (14 dígitos)."""
    if len(digitos) != 14 or digitos == digitos[0] * 14:
        return False
    return digitos[-2:] == dv_cnpj(digitos[:12])


def sugerir_cnpj_completo(digitos: str):
    """Reconstrói um CNPJ ao qual falta só o último dígito do DV.

    Os dois documentos truncados da planilha real (L143 e L228) perderam o
    SEGUNDO dígito verificador, não um zero à esquerda. Como os 12 dígitos
    de base e o primeiro DV continuam íntegros, o CNPJ completo é
    determinístico — e propor o valor exato evita o ciclo de o operador
    tentar "corrigir" acrescentando um zero na frente.
    """
    if len(digitos) != 13:
        return None
    completo = digitos[:12] + dv_cnpj(digitos[:12])
    return completo if completo[12] == digitos[12] else None


def cpf_valido(digitos: str) -> bool:
    """Valida os dois dígitos verificadores de um CPF (11 dígitos)."""
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        return False

    def dv(nums, peso_inicial):
        total = sum(int(n) * p for n, p in zip(nums, range(peso_inicial, 1, -1)))
        resto = (total * 10) % 11
        return "0" if resto == 10 else str(resto)

    d1 = dv(digitos[:9], 10)
    d2 = dv(digitos[:9] + d1, 11)
    return digitos[-2:] == d1 + d2


def classificar_documento(bruto):
    """
    Classifica o documento do tomador.

    Retorna (tipo, digitos, mensagem_de_erro_ou_None), onde tipo é um de:
    'CNPJ', 'CPF', 'AUSENTE', 'TRUNCADO', 'INVALIDO'.
    """
    texto = str(bruto).strip() if bruto is not None else ""
    if not texto or texto.lower() in {"x", "-", "none"}:
        return "AUSENTE", "", "Sem CNPJ/CPF — cadastro incompleto, impede a emissão"

    digitos = so_digitos(texto)
    if not digitos:
        return "AUSENTE", "", f"Documento '{texto}' não contém dígitos"

    if len(digitos) not in (11, 14):
        sugestao = sugerir_cnpj_completo(digitos)
        if sugestao:
            complemento = (
                f" Os 12 dígitos de base e o 1º dígito verificador estão íntegros: "
                f"o CNPJ completo só pode ser {sugestao} "
                f"({sugestao[:2]}.{sugestao[2:5]}.{sugestao[5:8]}/{sugestao[8:12]}-{sugestao[12:]}). "
                "Confirmar com o 2R antes de corrigir."
            )
        else:
            complemento = " Provável truncamento ou zero à esquerda perdido"
        return ("TRUNCADO", digitos,
                f"Documento '{texto}' tem {len(digitos)} dígitos — "
                f"esperado 14 (CNPJ) ou 11 (CPF).{complemento}")

    if len(digitos) == 14:
        if not cnpj_valido(digitos):
            return "INVALIDO", digitos, f"CNPJ '{texto}' não passa na validação de dígitos verificadores"
        return "CNPJ", digitos, None

    if not cpf_valido(digitos):
        return "INVALIDO", digitos, f"CPF '{texto}' não passa na validação de dígitos verificadores"
    return "CPF", digitos, None


def nome_base(nome) -> str:
    """
    Extrai o 'nome-base' de um cadastro, para comparar duplicatas.

    'FULANO DE TAL - FAZENDA A' e 'FULANO DE TAL - FAZENDA B' têm o mesmo
    nome-base ('FULANO DE TAL'): mesma pessoa, estabelecimentos
    diferentes. Já 'EMPRESA X LTDA' não bate com 'BELTRANO DA SILVA'.
    """
    texto = remove_acentos(str(nome if nome is not None else "")).upper()
    texto = re.split(r"\s+-\s+", texto)[0]
    texto = re.sub(r"[^A-Z0-9 ]", " ", texto)
    tokens = [t for t in texto.split() if t and t not in SUFIXOS_SOCIETARIOS]
    return " ".join(tokens)


def mesmo_titular(nomes) -> bool:
    """True somente se TODOS os cadastros tiverem exatamente o mesmo nome-base.

    Deliberadamente estrito. A versão anterior aceitava similaridade
    aproximada e rebaixava para AVISO casos como 'JOÃO SILVA SANTOS' x
    'JOSÉ SILVA SANTOS' (pessoas diferentes, blocos adjacentes na
    planilha) e matriz x filial — que são justamente as vizinhanças onde o
    arrasto de célula no Excel repete o CNPJ. Matriz e filial têm CNPJs
    diferentes: documento repetido entre elas é ERRO, não coincidência.
    """
    return len({nome_base(n) for n in nomes}) == 1


# "1.500" / "2.890" em célula de TEXTO é separador de milhar do padrão
# pt-BR. Sem esta regra, R$ 1.500,00 colado como texto viraria 1.5 sem
# nenhum erro visível (o Excel continuaria exibindo "R$ 1.500,00").
# O primeiro dígito não pode ser 0 para não capturar frações como "0.050".
_PADRAO_MILHAR_BR = re.compile(r"^[1-9]\d{0,2}(\.\d{3})+$")


def converte_numero(bruto):
    """Converte célula em float; retorna None se não for numérico."""
    if bruto is None:
        return None
    if isinstance(bruto, bool):
        return None
    if isinstance(bruto, (int, float)):
        return float(bruto)
    texto = str(bruto).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("%", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif _PADRAO_MILHAR_BR.match(texto.lstrip("+-")):
        texto = texto.replace(".", "")
    try:
        return float(texto)
    except ValueError:
        return None


def texto_limpo(bruto) -> str:
    """Normaliza conteúdo textual de célula: strip + upper + sem acento."""
    return remove_acentos(str(bruto if bruto is not None else "")).strip().upper()


def descricao_com_competencia_vazia(descricao: str) -> bool:
    """Detecta 'COMPETÊNCIA:' seguido de vazio ou quebra de linha."""
    alvo = remove_acentos(str(descricao or "")).upper()
    return bool(re.search(r"COMPETENCIA\s*:\s*(?:\r?\n|$)", alvo))


def validar(caminho: Path):
    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb.active

    linha_cabecalho, cabecalho, colunas = detectar_cabecalho(ws)
    if not colunas:
        raise SystemExit(
            f"Não foi possível localizar a linha de cabeçalho nas primeiras "
            f"{MAX_LINHAS_BUSCA_CABECALHO} linhas de '{caminho.name}'."
        )

    faltando = [c for c in ("empresa", "documento", "valor", "vencimento") if c not in colunas]
    if faltando:
        raise SystemExit(
            f"Planilha sem colunas obrigatórias: {faltando}. "
            f"Cabeçalho detectado na linha {linha_cabecalho}: {cabecalho}"
        )

    tem_descricao = "descricao" in colunas
    tem_retencao = "retencao_iss" in colunas
    tem_aliquota = "aliquota_iss" in colunas

    problemas = []
    mescladas = mapa_celulas_mescladas(ws)
    linhas_com_merge = []
    documentos_vistos = defaultdict(list)
    descricoes_especificas = []
    roster_atual = []
    estatisticas = {
        "linhas": 0,
        "cnpj": 0,
        "cpf": 0,
        "documento_problema": 0,
        "soma_valores": 0.0,
        "com_retencao_iss": 0,
    }

    def registra(severidade, num_linha, empresa, tipo, detalhe):
        problemas.append((severidade, num_linha, empresa, tipo, detalhe))

    # Coluna opcional que não é encontrada falharia ABERTO: a regra inteira
    # que depende dela seria pulada em silêncio, com exit code 0. Renomear as
    # duas colunas de ISS apagaria a retenção das 3 empresas que retêm; perder
    # a coluna de descrição desligaria a trava de "COMPETÊNCIA:" em branco.
    # Por isso ausência de coluna é ERRO estrutural, não observação.
    for chave, rotulo in (
        ("descricao", "DESCRIÇÃO DA NOTA"),
        ("retencao_iss", "RETENÇÃO DE ISS?"),
        ("aliquota_iss", "VALOR ALIQUOTA ISS"),
    ):
        if chave not in colunas:
            registra(SEVERIDADE_ERRO, None, None, "COLUNA_AUSENTE",
                     f"Coluna '{rotulo}' não encontrada no cabeçalho da linha "
                     f"{linha_cabecalho}. As regras que dependem dela seriam puladas "
                     f"em silêncio. Cabeçalho lido: {cabecalho}")

    for linha in ws.iter_rows(min_row=linha_cabecalho + 1):
        valores, herdados = valores_com_merge(linha, mescladas)
        if all(str(v).strip() == "" for v in valores if v is not None) and not any(
            isinstance(v, (int, float)) for v in valores
        ):
            continue

        num_linha = linha[0].row
        herdados_relevantes = {
            chave for chave, indice in colunas.items() if indice in herdados
        }

        def celula(chave):
            indice = colunas.get(chave)
            if indice is None or indice >= len(valores):
                return None
            return valores[indice]

        empresa_bruta = celula("empresa")
        empresa = str(empresa_bruta).strip() if empresa_bruta is not None else ""
        if not empresa:
            registra(SEVERIDADE_ERRO, num_linha, None, "EMPRESA_AUSENTE",
                     "Linha com dados mas sem nome da empresa")
            continue

        estatisticas["linhas"] += 1

        if herdados_relevantes:
            linhas_com_merge.append(num_linha)
            registra(SEVERIDADE_AVISO, num_linha, empresa, "CELULA_MESCLADA",
                     f"Campo(s) {sorted(herdados_relevantes)} vêm de célula MESCLADA com a "
                     "linha de cima — a célula desta linha está tecnicamente vazia. Funciona, "
                     "mas mesclar células numa planilha que alimenta automação é frágil: "
                     "desfazer a mesclagem e repetir o valor")

        if "MATRIZ E FILIA" in remove_acentos(empresa).upper():
            registra(SEVERIDADE_AVISO, num_linha, empresa, "CADASTRO_AGREGADO_MATRIZ_FILIAL",
                     "Nome declara matriz E filiais num único cadastro, com um só CNPJ e um só "
                     "valor. No resto da planilha a convenção é uma linha (e uma nota) por "
                     "estabelecimento. Confirmar com o 2R se é uma nota só ou várias")

        # ---------- Documento (CNPJ ou CPF) ----------
        doc_bruto = celula("documento")
        tipo_doc, digitos, erro_doc = classificar_documento(doc_bruto)

        if tipo_doc == "CNPJ":
            estatisticas["cnpj"] += 1
        elif tipo_doc == "CPF":
            estatisticas["cpf"] += 1
        else:
            estatisticas["documento_problema"] += 1

        if erro_doc:
            tipo_problema = {
                "AUSENTE": "DOCUMENTO_AUSENTE",
                "TRUNCADO": "DOCUMENTO_TRUNCADO",
                "INVALIDO": "DOCUMENTO_INVALIDO",
            }[tipo_doc]
            registra(SEVERIDADE_ERRO, num_linha, empresa, tipo_problema, erro_doc)
        else:
            documentos_vistos[digitos].append((num_linha, empresa, tipo_doc))
            # Identidade de uma empresa no roster = documento + nome, não a
            # linha (a linha se desloca toda vez que alguém entra ou sai).
            roster_atual.append((digitos, empresa))

        if digitos and digitos == CNPJ_PRESTADOR:
            registra(SEVERIDADE_ERRO, num_linha, empresa, "DOCUMENTO_IGUAL_AO_PRESTADOR",
                     f"CRÍTICO: documento {digitos} é o CNPJ do PRÓPRIO PRESTADOR — "
                     "a nota sairia da empresa emitente para ela mesma. Corrigir antes de emitir")

        # ---------- Valor ----------
        valor_bruto = celula("valor")
        valor = converte_numero(valor_bruto)
        if valor_bruto in (None, ""):
            registra(SEVERIDADE_ERRO, num_linha, empresa, "VALOR_AUSENTE", "Campo VALOR vazio")
        elif valor is None:
            registra(SEVERIDADE_ERRO, num_linha, empresa, "VALOR_NAO_NUMERICO",
                     f"VALOR '{valor_bruto}' não é numérico")
        elif valor <= 0:
            registra(SEVERIDADE_ERRO, num_linha, empresa, "VALOR_INVALIDO",
                     f"VALOR {valor} precisa ser maior que zero")
        else:
            estatisticas["soma_valores"] += valor
            if round(valor, 2) != valor:
                registra(SEVERIDADE_AVISO, num_linha, empresa, "VALOR_COM_FRACAO_DE_CENTAVO",
                         f"VALOR {valor} tem mais de 2 casas decimais. O portal trabalha em "
                         "centavos; o arredondamento aplicado por ele pode não coincidir com o "
                         "calculado aqui. Arredondar o valor na planilha")

        # ---------- Vencimento (dia do mês, 1..31) ----------
        venc_bruto = celula("vencimento")
        if venc_bruto in (None, ""):
            registra(SEVERIDADE_ERRO, num_linha, empresa, "VENCIMENTO_AUSENTE",
                     "Campo VENC vazio — sem dia de vencimento não dá para agendar a emissão")
        elif isinstance(venc_bruto, (datetime.datetime, datetime.date)):
            registra(SEVERIDADE_AVISO, num_linha, empresa, "VENCIMENTO_COMO_DATA",
                     f"VENC veio como data ({venc_bruto}); esperado o dia do mês. "
                     f"Assumindo dia {venc_bruto.day}")
        else:
            dia = converte_numero(venc_bruto)
            if dia is None or dia != int(dia):
                registra(SEVERIDADE_ERRO, num_linha, empresa, "VENCIMENTO_INVALIDO",
                         f"VENC '{venc_bruto}' não é um dia do mês inteiro")
            elif not 1 <= int(dia) <= 31:
                registra(SEVERIDADE_ERRO, num_linha, empresa, "VENCIMENTO_FORA_INTERVALO",
                         f"VENC {int(dia)} fora do intervalo 1..31")

        # ---------- Descrição (vazio NÃO é erro: herda a descrição padrão) ----------
        if tem_descricao:
            descricao_bruta = celula("descricao")
            descricao = str(descricao_bruta).strip() if descricao_bruta is not None else ""
            if descricao:
                descricoes_especificas.append((num_linha, empresa, descricao))
                if descricao_com_competencia_vazia(descricao):
                    registra(SEVERIDADE_AVISO, num_linha, empresa, "DESCRICAO_COMPETENCIA_VAZIA",
                             "Descrição tem 'COMPETÊNCIA:' sem valor — campo preenchido "
                             "manualmente a cada mês; o robô precisa receber mês/ano de competência")

        # ---------- Retenção de ISS: colunas devem ser coerentes ----------
        if tem_retencao or tem_aliquota:
            retencao_bruta = celula("retencao_iss") if tem_retencao else None
            aliquota_bruta = celula("aliquota_iss") if tem_aliquota else None

            retencao_txt = texto_limpo(retencao_bruta)
            tem_marca_retencao = bool(retencao_txt) and retencao_txt not in VALORES_NAO
            aliquota = converte_numero(aliquota_bruta)
            tem_aliquota_preenchida = aliquota_bruta not in (None, "")

            if tem_marca_retencao and retencao_txt not in VALORES_SIM:
                registra(SEVERIDADE_AVISO, num_linha, empresa, "RETENCAO_ISS_VALOR_ESTRANHO",
                         f"Coluna de retenção com valor '{retencao_bruta}' — esperado SIM/NÃO ou vazio")

            if tem_marca_retencao and not tem_aliquota_preenchida:
                registra(SEVERIDADE_ERRO, num_linha, empresa, "RETENCAO_ISS_SEM_ALIQUOTA",
                         f"Retenção marcada como '{str(retencao_bruta).strip()}' mas alíquota vazia — "
                         "colunas incoerentes")
            elif tem_aliquota_preenchida and not tem_marca_retencao:
                registra(SEVERIDADE_ERRO, num_linha, empresa, "ALIQUOTA_ISS_SEM_RETENCAO",
                         f"Alíquota '{aliquota_bruta}' preenchida mas coluna de retenção vazia — "
                         "colunas incoerentes")

            if tem_aliquota_preenchida:
                if aliquota is None:
                    registra(SEVERIDADE_ERRO, num_linha, empresa, "ALIQUOTA_ISS_NAO_NUMERICA",
                             f"Alíquota '{aliquota_bruta}' não é numérica")
                elif aliquota <= 0:
                    registra(SEVERIDADE_ERRO, num_linha, empresa, "ALIQUOTA_ISS_INVALIDA",
                             f"Alíquota {aliquota} precisa ser maior que zero")
                elif aliquota > ALIQUOTA_ISS_MAXIMA:
                    # Só é erro de ESCALA se o número faz sentido como pontos
                    # percentuais (>= 1). 0.06 é simplesmente alíquota acima do
                    # teto — sugerir "0.0006" mandaria o 2R corrigir errado.
                    if aliquota >= 1 and aliquota / 100 <= ALIQUOTA_ISS_MAXIMA:
                        registra(SEVERIDADE_ERRO, num_linha, empresa, "ALIQUOTA_ISS_ESCALA",
                                 f"Alíquota {aliquota} parece estar em pontos percentuais; "
                                 f"o esperado é a fração decimal ({aliquota / 100:.4f}). "
                                 "Erro de escala calcularia ISS 100x maior")
                    else:
                        registra(SEVERIDADE_ERRO, num_linha, empresa, "ALIQUOTA_ISS_FORA_INTERVALO",
                                 f"Alíquota {aliquota} acima do teto plausível de ISS "
                                 f"({ALIQUOTA_ISS_MAXIMA:.0%})")
                elif aliquota < ALIQUOTA_ISS_MINIMA_PLAUSIVEL:
                    registra(SEVERIDADE_AVISO, num_linha, empresa, "ALIQUOTA_ISS_ABAIXO_DO_PISO",
                             f"Alíquota {aliquota} ({aliquota:.2%}) abaixo do piso plausível de "
                             f"{ALIQUOTA_ISS_MINIMA_PLAUSIVEL:.0%} no Simples Nacional — conferir "
                             "se não faltou um dígito (ex.: 0.0041 no lugar de 0.0419)")

            if tem_marca_retencao:
                estatisticas["com_retencao_iss"] += 1

    # ---------- Duplicatas de documento ----------
    for digitos, ocorrencias in documentos_vistos.items():
        if len(ocorrencias) < 2:
            continue
        onde = ", ".join(f"L{n} ({e})" for n, e, _ in ocorrencias)
        tipo_doc = ocorrencias[0][2]
        nomes = [e for _, e, _ in ocorrencias]
        linhas = sorted(n for n, _, _ in ocorrencias)
        consecutivas = all(b - a == 1 for a, b in zip(linhas, linhas[1:]))
        dica = (" Linhas consecutivas — assinatura típica de arrasto/cópia de célula no Excel; "
                "conferir o documento correto no cadastro anterior.") if consecutivas else ""
        if mesmo_titular(nomes):
            registra(SEVERIDADE_AVISO, None, None, "DOCUMENTO_DUPLICADO_MESMO_TITULAR",
                     f"{tipo_doc} {digitos} repetido com o mesmo titular — provavelmente "
                     f"legítimo (vários estabelecimentos/contratos): {onde}. Confirmar com o 2R "
                     "se são notas separadas")
        else:
            registra(SEVERIDADE_ERRO, None, None, "DOCUMENTO_DUPLICADO_NOMES_DIVERGENTES",
                     f"{tipo_doc} {digitos} repetido em empresas de nomes distintos — "
                     f"provável erro de cadastro: {onde}.{dica}")

    contexto = {
        "linha_cabecalho": linha_cabecalho,
        "cabecalho": cabecalho,
        "colunas": colunas,
        "tem_descricao": tem_descricao,
        "tem_retencao": tem_retencao,
        "tem_aliquota": tem_aliquota,
        "descricoes_especificas": descricoes_especificas,
        "estatisticas": estatisticas,
        "linhas_com_merge": linhas_com_merge,
        "roster_atual": roster_atual,
    }
    return problemas, contexto


def chave_roster(documento: str, empresa: str) -> str:
    return f"{documento}|{empresa}"


def carregar_roster_anterior(caminho: Path):
    """Lê o roster salvo na última validação (conjunto de "documento|empresa").

    None se ainda não existir (primeira execução) ou estiver corrompido —
    em nenhum dos dois casos a validação da planilha deve travar por causa
    do snapshot de comparação.
    """
    if not caminho.exists():
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return set(dados) if isinstance(dados, list) else None
    except (OSError, ValueError):
        return None


def salvar_roster(caminho: Path, roster_atual: list) -> None:
    """Grava o roster desta rodada para comparar na próxima execução."""
    chaves = sorted({chave_roster(documento, empresa) for documento, empresa in roster_atual})
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(chaves, ensure_ascii=False, indent=2), encoding="utf-8")


def comparar_roster(anterior: set, roster_atual: list):
    """Retorna (entraram, sairam) — pares (documento, empresa) — desde a última execução.

    O cadastro do 2R cresce e encolhe todo mês (contrato novo, contrato
    encerrado). Isso é esperado, não é erro — mas precisa aparecer na tela,
    não sumir em silêncio: foi assim que 19 empresas saíram entre duas
    rodadas sem que ninguém tivesse marcado isso em lugar nenhum.
    """
    atuais = {chave_roster(documento, empresa) for documento, empresa in roster_atual}
    entraram = sorted(tuple(c.split("|", 1)) for c in atuais - anterior)
    sairam = sorted(tuple(c.split("|", 1)) for c in anterior - atuais)
    return entraram, sairam


def imprimir_mudancas_cadastro(entraram, sairam):
    if not entraram and not sairam:
        print("\nCadastro igual ao da última validação — nenhuma empresa entrou ou saiu.")
        return
    print("\n" + "=" * 70)
    print(f"MUDANÇAS NO CADASTRO desde a última validação: "
          f"{len(entraram)} entraram / {len(sairam)} saíram")
    print("=" * 70)
    if entraram:
        print("  Entraram:")
        for documento, empresa in entraram:
            print(f"    + {empresa} ({documento})")
    if sairam:
        print("  Saíram (não constam mais na planilha):")
        for documento, empresa in sairam:
            print(f"    - {empresa} ({documento})")
    print("  Isso é esperado (contratos novos/encerrados) — confirme que bate com o "
          "que o 2R avisou antes de seguir para a emissão.")


def salvar_relatorio(problemas, caminho_saida: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ocorrências"
    ws.append(["Severidade", "Linha", "Empresa", "Tipo", "Detalhe"])
    ordem = {SEVERIDADE_ERRO: 0, SEVERIDADE_AVISO: 1}
    for severidade, linha, empresa, tipo, detalhe in sorted(
        problemas, key=lambda p: (ordem.get(p[0], 9), p[1] if p[1] is not None else 10**9)
    ):
        ws.append([severidade, linha, empresa, tipo, detalhe])
    for coluna, largura in zip("ABCDE", (12, 8, 45, 36, 90)):
        ws.column_dimensions[coluna].width = largura
    wb.save(caminho_saida)


def imprimir_resumo(caminho: Path, problemas, contexto):
    est = contexto["estatisticas"]
    erros = [p for p in problemas if p[0] == SEVERIDADE_ERRO]
    avisos = [p for p in problemas if p[0] == SEVERIDADE_AVISO]

    print(f"Planilha: {caminho.name}")
    print(f"Cabeçalho detectado na linha {contexto['linha_cabecalho']}: {contexto['cabecalho']}")
    print(f"Colunas mapeadas: " + ", ".join(f"{k}={v}" for k, v in sorted(contexto["colunas"].items())))
    if contexto["linhas_com_merge"]:
        print(f"Células mescladas resolvidas em {len(contexto['linhas_com_merge'])} linha(s): "
              + ", ".join(f"L{n}" for n in contexto["linhas_com_merge"]))

    print("\n" + "=" * 70)
    print("ESTATÍSTICAS")
    print("=" * 70)
    print(f"  Total de empresas (linhas com dados): {est['linhas']}")
    print(f"  Documentos CNPJ válidos:              {est['cnpj']}")
    print(f"  Documentos CPF válidos:               {est['cpf']}")
    print(f"  Documentos com problema:              {est['documento_problema']}")
    print(f"  Soma dos valores:                     R$ {est['soma_valores']:,.2f}"
          .replace(",", "#").replace(".", ",").replace("#", "."))
    print(f"  Linhas com retenção de ISS:           {est['com_retencao_iss']}")

    descricoes = contexto["descricoes_especificas"]
    print("\n" + "=" * 70)
    print(f"DESCRIÇÕES ESPECÍFICAS PREENCHIDAS: {len(descricoes)}")
    print("=" * 70)
    if not descricoes:
        print("  (nenhuma — todas herdam a descrição padrão)")
    for num_linha, empresa, descricao in descricoes:
        resumo = " / ".join(t.strip() for t in descricao.splitlines() if t.strip())
        if len(resumo) > 110:
            resumo = resumo[:107] + "..."
        print(f"  L{num_linha} {empresa}")
        print(f"       -> {resumo}")

    print("\n" + "=" * 70)
    print(f"OCORRÊNCIAS: {len(erros)} ERRO(S) / {len(avisos)} AVISO(S)")
    print("=" * 70)
    for rotulo, lista in ((SEVERIDADE_ERRO, erros), (SEVERIDADE_AVISO, avisos)):
        if not lista:
            continue
        contagem = Counter(tipo for _, _, _, tipo, _ in lista)
        print(f"\n  {rotulo}:")
        for tipo, qtd in sorted(contagem.items()):
            print(f"    - {tipo}: {qtd}")

    if erros:
        print("\n  Detalhe dos ERROS:")
        for _, num_linha, empresa, tipo, detalhe in sorted(
            erros, key=lambda p: p[1] if p[1] is not None else 10**9
        ):
            onde = f"L{num_linha}" if num_linha is not None else "-"
            quem = f" {empresa}" if empresa else ""
            print(f"    [{onde}]{quem} | {tipo}: {detalhe}")

    if avisos:
        print("\n  Detalhe dos AVISOS:")
        for _, num_linha, empresa, tipo, detalhe in sorted(
            avisos, key=lambda p: p[1] if p[1] is not None else 10**9
        ):
            onde = f"L{num_linha}" if num_linha is not None else "-"
            quem = f" {empresa}" if empresa else ""
            print(f"    [{onde}]{quem} | {tipo}: {detalhe}")


def main():
    # O console do Windows costuma usar cp1252 e corromper acentos.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:  # pragma: no cover - Python antigo
        pass

    parser = argparse.ArgumentParser(description="Validador da planilha de notas fiscais do 2R.")
    parser.add_argument("planilha", type=Path, help="Caminho da planilha de controle (.xlsx)")
    parser.add_argument("--saida", type=Path, default=None, help="Caminho do relatório (.xlsx)")
    parser.add_argument(
        "--roster", type=Path, default=None,
        help="Snapshot de cadastro para comparar mudanças mês a mês "
             "(padrão: estado/roster_empresas.json na pasta do projeto)",
    )
    args = parser.parse_args()

    if not args.planilha.exists():
        sys.exit(f"Arquivo não encontrado: {args.planilha}")

    problemas, contexto = validar(args.planilha)
    imprimir_resumo(args.planilha, problemas, contexto)

    caminho_roster = args.roster or Path(__file__).resolve().parent.parent / "estado" / "roster_empresas.json"
    roster_anterior = carregar_roster_anterior(caminho_roster)
    if roster_anterior is None:
        print("\n(Primeira execução com controle de cadastro — nada para comparar ainda.)")
    else:
        entraram, sairam = comparar_roster(roster_anterior, contexto["roster_atual"])
        imprimir_mudancas_cadastro(entraram, sairam)
    salvar_roster(caminho_roster, contexto["roster_atual"])

    erros = [p for p in problemas if p[0] == SEVERIDADE_ERRO]

    if problemas:
        saida = args.saida or args.planilha.with_name(args.planilha.stem + "_ocorrencias.xlsx")
        salvar_relatorio(problemas, saida)
        print(f"\nRelatório detalhado salvo em: {saida}")

    if erros:
        print(f"\n=> BLOQUEANTE: {len(erros)} erro(s) precisam de correção antes da emissão.")
        sys.exit(1)

    print("\nSem erros bloqueantes. Planilha pronta para a Fase 2 (automação de emissão).")


if __name__ == "__main__":
    main()
