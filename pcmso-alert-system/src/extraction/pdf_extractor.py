"""
Extrator de dados de PDFs PCMSO.
Pipeline híbrido: PyPDF2 (texto) + pdfplumber (tabelas) + regex (campos estruturados).
Cobre empresa, cargos, riscos, exames periódicos e mapeamento cargo×exame.

Colaboradores NÃO são extraídos do PCMSO — chegam via demanda dos técnicos.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import pdfplumber
import PyPDF2

from src.extraction.duplicate_checker import calcular_hash_arquivo
from src.extraction.validators import formatar_cnpj, formatar_cpf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Tudo que é específico do layout do prestador fica agrupado aqui.
PERFIL_PRESTADOR = {
    "nome": "Prevenclínica",
    "cnpj_parcial": "43.453.808",  # parcial — bate em "0001-37" e "0001 -37"
    "ancora_dados": r"01\s*[–\-]\s*DADOS",
    "ancora_cargos": r"QUADRO\s+DE\s+CARGOS",
    # Tabelas cargo×exame: uma por cargo, intituladas "CONTROLE MÉDICO – CARGOS: X"
    "ancora_controle_medico": r"CONTROLE\s+M[ÉE]DICO\s*[–\-—]*\s*CARGOS?\s*:?\s*([^\n]+)",
}

CNPJ_PREVENCLÍNICA = PERFIL_PRESTADOR["cnpj_parcial"]

TIPOS_RISCO: dict[str, list[str]] = {
    "ERGONÔMICO": ["ergon", "postura", "repetit", "esfor", "levantamento", "bipedest"],
    "MECÂNICO": ["mecân", "mecanic", "máquin", "maquin", "ferram", "cortante", "perfurante", "impacto"],
    "ELÉTRICO": ["elétr", "eletr", "tensão", "tensao", "choque", "curto"],
    "TRABALHO EM ALTURA": ["altura", "queda", "andaime", "escada"],
    "PSICOSSOCIAL": ["psicoss", "estress", "assédio", "assedio", "pressão", "pressao"],
}


# ---------------------------------------------------------------------------
# Padrões Regex para documentos PCMSO brasileiros
# ---------------------------------------------------------------------------

PCMSO_PATTERNS = {
    # Campos da seção 01 – DADOS (estrutura real dos PDFs Prevenclínica)
    "razao_social":      r"Raz[aã]o\s+[Ss]ocial[:\s]+([^\n]+?)(?:\s{3,}|Grau\s+de|$)",
    "cnpj":              r"CNPJ[:\s]*([\d]{2}\.[\d]{3}\.[\d]{3}/[\d]{4}\s*[-–]\s*[\d]{2})",
    "grau_risco":        r"Grau\s+de\s+[Rr]isco[:\s]*(\d{1,2})",
    "endereco":          r"Endere[çc]o[:\s]+([^\n]+)",
    "cnae":              r"CNAE[:\s]*([\d]{2}\.[\d]{2,3}[-–][\d]-[\d]{2})",
    "num_profissionais": r"[Nn][úu]mero\s+de\s+profissionais[:\s]*(\d+)",
    "responsavel":       r"Respons[áa]vel\s+pela\s+empresa[:\s]+([^\n]+?)(?:\s*\n|\s*Contato|$)",
    "medico_pcmso":      r"Resp\.\s+PCMSO[:\s]+([^\n]+?)(?:\s+CRM|\s*$)",
    "vigencia_inicio":   r"[Ii]n[íi]cio\s+da\s+vig[êe]ncia[:\s]*([\d][\d\s/]{3,9})",
    "vigencia_fim":      r"[Ff]im\s+da\s+vig[êe]ncia[:\s]*([\d][\d\s/]{3,9})",
    "email_sso":         r"(?:E-mail|Email|e-mail)[:\s]*([\w\.\-]+@[\w\.\-]+\.\w+)",
    "whatsapp":          r"(?:[Cc]ontato|WhatsApp|Whats)[:\s]*([\(\d\)\s\-\+\.]{8,20})",
    "nome_fantasia":     r"(?:Nome\s+[Ff]antasia|Nome\s+[Cc]omercial)[:\s]+([^\n]+)",
}

HEADERS_CARGO_EXAMES = [
    "cargo", "função", "funcao", "risco", "agente", "exame", "procedimento", "periodicidade",
]


# ---------------------------------------------------------------------------
# Filtro de cabeçalho do prestador
# ---------------------------------------------------------------------------

def _filtrar_cabecalho_prevenclínica(texto: str) -> str:
    """Remove linhas que contenham o CNPJ da Prevenclínica (prestador de serviço)."""
    linhas = texto.splitlines()
    return "\n".join(l for l in linhas if CNPJ_PREVENCLÍNICA not in l)


# ---------------------------------------------------------------------------
# Análise estrutural do PDF
# ---------------------------------------------------------------------------

def analisar_pdf(filepath: str | Path) -> dict:
    """Analisa a estrutura do PDF: número de páginas e quantidade de tabelas."""
    filepath = Path(filepath)
    resultado = {"tipo": "pdf", "paginas": 0, "tabelas": 0, "has_tables": False, "amostra_texto": ""}

    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        resultado["paginas"] = len(reader.pages)
        if reader.pages:
            resultado["amostra_texto"] = reader.pages[0].extract_text()[:500] or ""

    with pdfplumber.open(filepath) as pdf:
        total_tabelas = sum(len(page.extract_tables()) for page in pdf.pages)
        resultado["tabelas"] = total_tabelas
        resultado["has_tables"] = total_tabelas > 0

    logger.info(
        f"PDF analisado: {filepath.name} | "
        f"{resultado['paginas']} páginas | {resultado['tabelas']} tabelas"
    )
    return resultado


# ---------------------------------------------------------------------------
# Extração de texto completo
# ---------------------------------------------------------------------------

def extrair_texto_pdf(filepath: str | Path) -> str:
    """Extrai texto completo do PDF via PyPDF2."""
    texto = ""
    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            texto += (page.extract_text() or "") + "\n"
    return texto


# ---------------------------------------------------------------------------
# Extração de tabelas via pdfplumber
# ---------------------------------------------------------------------------

def extrair_tabelas_pdf(filepath: str | Path) -> list[dict]:
    """
    Extrai todas as tabelas do PDF.
    Retorna lista de dicts com página, número da tabela e DataFrame.
    """
    tabelas = []
    with pdfplumber.open(filepath) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, 1):
            tables = pagina.extract_tables()
            for num_tabela, table in enumerate(tables, 1):
                if table and len(table) > 1:
                    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(table[0])]
                    df = pd.DataFrame(table[1:], columns=headers)
                    df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
                    tabelas.append({
                        "pagina": num_pagina,
                        "tabela_num": num_tabela,
                        "dataframe": df,
                        "headers": headers,
                    })
    return tabelas


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers_match(headers: list[str], keywords: list[str], threshold: int = 2) -> bool:
    """Verifica se os headers contêm pelo menos `threshold` keywords."""
    headers_lower = [h.lower() for h in headers if h]
    matches = sum(1 for kw in keywords if any(kw in h for h in headers_lower))
    return matches >= threshold


def _parse_data_br(valor: str) -> Optional[date]:
    """Tenta converter string DD/MM/YYYY ou DD-MM-YYYY para date."""
    if not valor:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(valor).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _classificar_risco(descricao: str) -> str:
    """Classifica um risco em um dos TIPOS_RISCO com base em palavras-chave."""
    desc_lower = descricao.lower()
    for tipo, keywords in TIPOS_RISCO.items():
        if any(kw in desc_lower for kw in keywords):
            return tipo
    return "OUTRO"


# ---------------------------------------------------------------------------
# Extração por regex (texto livre)
# ---------------------------------------------------------------------------

def extrair_dados_empresa_por_regex(texto: str) -> dict:
    """
    Extrai dados da empresa a partir do trecho após '01 – DADOS'.
    Os PDFs da Prevenclínica seguem estrutura fixa: seção DADOS contém
    todos os campos da empresa cliente.
    """
    dados: dict = {
        "razao_social": "",
        "cnpj": "",
        "nome_fantasia": "",
        "grau_risco": "",
        "cnae": "",
        "endereco": "",
        "num_profissionais": "",
        "medico_pcmso": "",
        "responsavel_empresa": "",
        "vigencia_inicio": "",
        "vigencia_fim": "",
        "email_sso": "",
        "whatsapp_sso": "",
    }

    # Isolar a seção de dados da empresa — começa em "01 – DADOS"
    idx = re.search(PERFIL_PRESTADOR["ancora_dados"], texto, re.IGNORECASE)
    secao = texto[idx.start():idx.start() + 3000] if idx else texto[:3000]

    for campo, padrao in [
        ("razao_social",      PCMSO_PATTERNS["razao_social"]),
        ("cnpj",              PCMSO_PATTERNS["cnpj"]),
        ("grau_risco",        PCMSO_PATTERNS["grau_risco"]),
        ("endereco",          PCMSO_PATTERNS["endereco"]),
        ("cnae",              PCMSO_PATTERNS["cnae"]),
        ("num_profissionais", PCMSO_PATTERNS["num_profissionais"]),
        ("medico_pcmso",      PCMSO_PATTERNS["medico_pcmso"]),
        ("responsavel_empresa", PCMSO_PATTERNS["responsavel"]),
        ("email_sso",         PCMSO_PATTERNS["email_sso"]),
        ("whatsapp_sso",      PCMSO_PATTERNS["whatsapp"]),
        ("nome_fantasia",     PCMSO_PATTERNS["nome_fantasia"]),
    ]:
        match = re.search(padrao, secao, re.IGNORECASE | re.MULTILINE)
        if match:
            valor = match.group(1).strip()
            if campo == "cnpj":
                # Remove espaços internos que o PyPDF2 insere (ex: "0001 -36" → "0001-36")
                valor = re.sub(r'\s+', '', valor)
                valor = formatar_cnpj(valor)
            dados[campo] = valor

    # Vigência: página de capa traz "Início da vigência: MM/AAAA" e "Fim da vigência: MM/AAAA"
    # PyPDF2 pode inserir espaço no ano: "09/202 5" → normalizar para "09/2025"
    # Buscar em todo o texto pois pode estar na página 1 (antes da seção DADOS)
    ini = re.search(PCMSO_PATTERNS["vigencia_inicio"], texto, re.IGNORECASE)
    fim = re.search(PCMSO_PATTERNS["vigencia_fim"], texto, re.IGNORECASE)
    if ini:
        dados["vigencia_inicio"] = re.sub(r'\s+', '', ini.group(1))
    if fim:
        dados["vigencia_fim"] = re.sub(r'\s+', '', fim.group(1))

    return dados


def _extrair_cargos_por_regex(texto: str) -> list[dict]:
    """
    Extrai lista de cargos da seção 'QUADRO DE CARGOS' dos PDFs Prevenclínica.
    Estrutura real: tabela com colunas Setor | Cargos | Quantidade de funcionários.
    Após o cabeçalho, cada linha é: "EST XXXX - NOME DO SETOR  NOME DO CARGO  NN"
    """
    cargos = []
    visto: set[tuple] = set()

    # Isolar o bloco QUADRO DE CARGOS
    ini = re.search(PERFIL_PRESTADOR["ancora_cargos"], texto, re.IGNORECASE)
    if not ini:
        return cargos

    # O bloco termina quando começa a próxima seção numerada (ex: "02 –" ou linha vazia longa)
    fim = re.search(r"\n\s*\d{2}\s*[–\-]", texto[ini.end():])
    bloco = texto[ini.end(): ini.end() + fim.start()] if fim else texto[ini.end(): ini.end() + 2000]

    # Normaliza espaços extras que o PyPDF2 insere dentro de tokens:
    # "EST 0 001" → "EST 0001", "GERENTE  GERAL" fica como está (dois espaços = separador)
    bloco_norm = re.sub(
        r'\bEST\s+(\d[\d\s]*)',
        lambda m: 'EST ' + re.sub(r'\s+', '', m.group(1)),
        bloco,
    )

    # Processa linha a linha — estrutura: "EST XXXX - SETOR  CARGO_TEXTO  QTD [datas...]"
    setor_pendente = ""
    for linha in bloco_norm.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        # Remove datas no final (artefato de algumas páginas): "02 12/09/2026 ..."
        linha_clean = re.sub(r'\s+\d{2}/\d{2}/\d{2,4}.*$', '', linha).strip()

        # Linha com EST: pode ter o cargo na mesma linha ou na próxima
        if re.match(r'EST\s*\d+\s*[-–]', linha_clean):
            # Tenta extrair na mesma linha: setor  cargo  qtd (onde qtd = último número)
            m_qtd = re.search(r'\s+(\d{1,4})\s*$', linha_clean)
            if m_qtd:
                qtd = m_qtd.group(1)
                partes = re.split(r'\s{2,}', linha_clean[:m_qtd.start()])
                if len(partes) >= 2:
                    setor = partes[0].strip()
                    cargo = '  '.join(partes[1:]).strip()  # une partes do cargo
                    # Remove sufixos como "(TELEFONE)" do início do cargo
                    cargo = re.sub(r'^\([^\)]+\)\s*', '', cargo).strip()
                    chave = (setor.upper(), cargo.upper())
                    if cargo and chave not in visto:
                        visto.add(chave)
                        cargos.append({"setor": setor, "cargo": cargo, "quantidade": qtd})
                    setor_pendente = ""
                    continue
            # Sem QTD na mesma linha → setor está sozinho, cargo virá na próxima
            setor_pendente = linha_clean
            continue

        # Linha sem EST, mas há um setor pendente da linha anterior
        if setor_pendente:
            m_qtd = re.search(r'\s+(\d{1,4})\s*$', linha_clean)
            if m_qtd:
                qtd = m_qtd.group(1)
                cargo_raw = linha_clean[:m_qtd.start()].strip()
                cargo = re.sub(r'^\([^\)]+\)\s*', '', cargo_raw).strip()
                chave = (setor_pendente.upper(), cargo.upper())
                if cargo and chave not in visto:
                    visto.add(chave)
                    cargos.append({"setor": setor_pendente, "cargo": cargo, "quantidade": qtd})
            setor_pendente = ""

    # Fallback: linha "CARGO  QTD" sem setor — captura linhas maiúsculas com número no final
    if not cargos:
        for linha in bloco.splitlines():
            m = re.match(r"^([A-ZÀÁÂÃÉÊÍÓÔÕÚ][A-ZÀ-Ú\s\-\/]{3,60}?)\s{2,}(\d{1,4})\s*$", linha.strip())
            if m:
                cargo = m.group(1).strip()
                qtd = m.group(2)
                if cargo.upper() not in visto:
                    visto.add(cargo.upper())
                    cargos.append({"setor": "", "cargo": cargo, "quantidade": qtd})

    return cargos


def _extrair_riscos_por_regex(texto: str) -> list[dict]:
    """
    Extrai riscos ocupacionais classificados a partir do texto do PCMSO.
    Retorna lista de {tipo_risco, descricao_risco, danos_saude}.
    """
    riscos = []
    visto: set[tuple] = set()

    # Padrão: RISCO: <descrição> / DANO: <dano>
    padrao = re.compile(
        r"(?:RISCO|Risco)[:\s]+([^\n/]{5,100}?)(?:\s*[/\n]\s*(?:DANO|Dano|Consequência|consequencia)[:\s]+([^\n]{5,100}))?",
        re.IGNORECASE,
    )
    for m in padrao.finditer(texto):
        descricao = m.group(1).strip()
        dano = (m.group(2) or "").strip()
        tipo = _classificar_risco(descricao)
        chave = (tipo, descricao.upper()[:60])
        if chave not in visto:
            visto.add(chave)
            riscos.append({"tipo_risco": tipo, "descricao_risco": descricao, "danos_saude": dano})

    return riscos


def _extrair_exames_pcmso_por_regex(texto: str) -> list[dict]:
    """
    Extrai exames periódicos definidos no PCMSO (por tipo/periodicidade, NÃO por colaborador).
    Retorna lista de {exame, periodicidade}.
    """
    exames = []
    visto: set[str] = set()

    TIPOS_EXAMES = [
        "audiometria", "acuidade visual", "hemograma", "espirometria",
        "eletrocardiograma", "ecg", "raio-x", "radiografia", "glicemia",
        "colesterol", "triglicérides", "triglicerides", "urina", "parasitológico",
        "avaliação clínica", "avaliacao clinica", "exame médico", "exame medico",
        "eletroencefalograma", "eeg", "toxicológico", "toxicologico",
        "bioquímica", "bioquimica", "creatinina", "tgo", "tgp",
    ]

    for tipo in TIPOS_EXAMES:
        # Busca "audiometria ... anual" ou "audiometria ... 12 meses"
        padrao = re.compile(
            rf"({re.escape(tipo)}[^\n]{{0,60}}?)"
            r"(anual|semestral|trimestral|\d+\s*meses?)",
            re.IGNORECASE,
        )
        for m in padrao.finditer(texto):
            nome = tipo.title()
            periodicidade = m.group(2).strip().lower()
            if nome.lower() not in visto:
                visto.add(nome.lower())
                exames.append({"exame": nome, "periodicidade": periodicidade})

    return exames


# ---------------------------------------------------------------------------
# Extração de tabela cargo×exame via pdfplumber
# ---------------------------------------------------------------------------

def _extrair_cargo_exames_de_tabela(df: pd.DataFrame) -> list[dict]:
    """Extrai mapeamento cargo/risco → exames da tabela de riscos do PCMSO."""
    cargo_exames = []
    cols_lower = {c.lower(): c for c in df.columns}

    col_cargo = next((cols_lower[k] for k in cols_lower if "cargo" in k or "função" in k or "funcao" in k), None)
    col_setor = next((cols_lower[k] for k in cols_lower if "setor" in k), None)
    col_risco = next((cols_lower[k] for k in cols_lower if "risco" in k or "agente" in k), None)
    col_exame = next((cols_lower[k] for k in cols_lower if "exame" in k or "procedimento" in k), None)
    col_period = next((cols_lower[k] for k in cols_lower if "period" in k), None)

    if not col_cargo or not col_exame:
        return []

    for _, row in df.iterrows():
        cargo = str(row[col_cargo]).strip() if pd.notna(row[col_cargo]) else ""
        exame = str(row[col_exame]).strip() if pd.notna(row[col_exame]) else ""

        if not cargo or not exame or cargo.lower() in ("nan", "none"):
            continue

        entry = {
            "cargo": cargo,
            "setor": str(row[col_setor]).strip() if col_setor and pd.notna(row[col_setor]) else "",
            "risco": str(row[col_risco]).strip() if col_risco and pd.notna(row[col_risco]) else "",
            "tipo_exame": exame,
            "periodicidade_meses": None,
        }

        if col_period and pd.notna(row[col_period]):
            nums = re.findall(r"\d+", str(row[col_period]))
            if nums:
                entry["periodicidade_meses"] = int(nums[0])

        cargo_exames.append(entry)

    return cargo_exames


# ---------------------------------------------------------------------------
# Extração das tabelas CONTROLE MÉDICO (cargo×exame do layout Prevenclínica)
# ---------------------------------------------------------------------------

_RE_CONTROLE_MEDICO = re.compile(PERFIL_PRESTADOR["ancora_controle_medico"], re.IGNORECASE)
_RE_PERIODICIDADE = re.compile(r"cada\s+(\d{1,3})\s*m[êe]s", re.IGNORECASE)
_RE_MOMENTO = re.compile(r"Fazer\s+n[oa]\s+([^\n*]+)", re.IGNORECASE)


def _tabela_parece_controle_medico(table: list[list]) -> bool:
    """Heurística para tabelas CONTROLE MÉDICO cujo título ficou fora da tabela."""
    for row in table:
        for celula in row:
            if celula and (_RE_MOMENTO.search(str(celula)) or _RE_PERIODICIDADE.search(str(celula))):
                return True
    return False


def _parse_tabela_controle_medico(table: list[list], cargo: str) -> list[dict]:
    """
    Converte uma tabela CONTROLE MÉDICO em entradas cargo×exame.
    Estrutura: cada linha é um exame — col 0 = nome do exame, col 1 = momentos
    ("Fazer no Admissional..."), última col = periodicidade ("a cada 12 meses").
    Linhas de título embutido e rodapés (*) são ignoradas.
    """
    entradas: list[dict] = []
    for row in table:
        celulas = [str(c).strip() if c else "" for c in row]
        exame = celulas[0] if celulas else ""
        if not exame or exame.startswith("*") or _RE_CONTROLE_MEDICO.search(exame):
            continue
        resto = " ".join(c for c in celulas[1:] if c)
        if not resto:
            continue

        m_per = _RE_PERIODICIDADE.search(resto)
        entradas.append({
            "cargo": cargo,
            "setor": "",
            "risco": "",
            "tipo_exame": exame.rstrip(":").strip(),
            "periodicidade_meses": int(m_per.group(1)) if m_per else None,
            # por célula, para o match não vazar para a coluna seguinte
            "momentos": [m.strip() for c in celulas[1:] for m in _RE_MOMENTO.findall(c)],
        })
    return entradas


def extrair_cargo_exames_controle_medico(filepath: str | Path) -> list[dict]:
    """
    Extrai o mapeamento cargo×exame das tabelas "CONTROLE MÉDICO – CARGOS: X".
    O título pode vir como primeira linha da tabela ou solto no texto da página
    (o pdfplumber às vezes separa o título do corpo da tabela).
    """
    entradas: list[dict] = []
    with pdfplumber.open(filepath) as pdf:
        for pagina in pdf.pages:
            titulos = _RE_CONTROLE_MEDICO.findall(pagina.extract_text() or "")
            for table in pagina.extract_tables():
                if not table:
                    continue
                primeira_linha = " ".join(str(c) for c in table[0] if c)
                m = _RE_CONTROLE_MEDICO.search(primeira_linha)
                if m:
                    cargo = m.group(1)
                elif titulos and _tabela_parece_controle_medico(table):
                    cargo = titulos[0]
                else:
                    continue
                entradas.extend(_parse_tabela_controle_medico(table, cargo.strip(" :–-")))
    return entradas


# ---------------------------------------------------------------------------
# Score de confiança da extração
# ---------------------------------------------------------------------------

# Pesos dos campos críticos da empresa (cnpj e vigência são o coração dos alertas)
_PESOS_CAMPOS_EMPRESA = {
    "cnpj": 3,
    "vigencia_inicio": 2,
    "vigencia_fim": 2,
    "razao_social": 1,
    "email_sso": 1,
}


def calcular_confianca(resultado: dict, texto: str) -> dict:
    """
    Auto-avaliação da extração. Combina três sinais:
    - score_empresa: campos críticos preenchidos (ponderado)
    - score_estrutura: âncoras de seção encontradas + tabelas cargo×exame
    - score_volume: heurísticas mínimas de quantidade
    Retorna dict com scores, nível (ALTA/MEDIA/BAIXA) e avisos textuais.
    """
    avisos: list[str] = []
    empresa = resultado.get("empresa", {})

    # --- score_empresa ---
    total_peso = sum(_PESOS_CAMPOS_EMPRESA.values())
    peso_ok = 0
    for campo, peso in _PESOS_CAMPOS_EMPRESA.items():
        if str(empresa.get(campo, "")).strip():
            peso_ok += peso
        else:
            avisos.append(f"Campo '{campo}' não encontrado")
    score_empresa = peso_ok / total_peso

    # --- score_estrutura ---
    pontos_estrutura = 0
    if re.search(PERFIL_PRESTADOR["ancora_dados"], texto, re.IGNORECASE):
        pontos_estrutura += 1
    else:
        avisos.append("Seção '01 – DADOS' não encontrada — layout fora do padrão")
    if re.search(PERFIL_PRESTADOR["ancora_cargos"], texto, re.IGNORECASE):
        pontos_estrutura += 1
    else:
        avisos.append("Seção 'QUADRO DE CARGOS' não encontrada — layout fora do padrão")
    if resultado.get("cargo_exames"):
        pontos_estrutura += 1
    else:
        avisos.append("Nenhuma tabela cargo×exame extraída")
    score_estrutura = pontos_estrutura / 3

    # --- score_volume ---
    pontos_volume = 0
    if resultado.get("cargos"):
        pontos_volume += 1
    else:
        avisos.append("Nenhum cargo extraído")
    if resultado.get("cargo_exames"):
        pontos_volume += 1
    cnpj = str(empresa.get("cnpj", ""))
    if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", cnpj):
        pontos_volume += 1
    elif cnpj:
        avisos.append(f"CNPJ em formato inesperado: '{cnpj}'")
    score_volume = pontos_volume / 3

    score_geral = round(0.5 * score_empresa + 0.3 * score_estrutura + 0.2 * score_volume, 3)
    nivel = "ALTA" if score_geral >= 0.8 else "MEDIA" if score_geral >= 0.5 else "BAIXA"

    return {
        "score_empresa": round(score_empresa, 3),
        "score_estrutura": round(score_estrutura, 3),
        "score_volume": round(score_volume, 3),
        "score_geral": score_geral,
        "nivel": nivel,
        "avisos": avisos,
    }


# ---------------------------------------------------------------------------
# Pipeline principal de extração
# ---------------------------------------------------------------------------

def extrair_pcmso(filepath: str | Path) -> dict:
    """
    Pipeline completo de extração de dados de um PCMSO PDF.

    Estratégia híbrida:
    1. Extrai texto completo (PyPDF2) + filtra cabeçalho do prestador
    2. Aplica regex para empresa, cargos, riscos e exames periódicos
    3. Extrai tabelas (pdfplumber) para mapeamento cargo×exame
    4. Deduplica cargos e riscos
    5. Retorna JSON estruturado

    Retorna:
    {
        "arquivo": str,
        "hash": str,
        "empresa": {...},
        "cargos": [...],
        "riscos": [...],
        "exames": [...],
        "cargo_exames": [...],
        "erros_extracao": [str]
    }
    """
    filepath = Path(filepath)
    logger.info(f"Iniciando extração: {filepath.name}")

    resultado: dict = {
        "arquivo": filepath.name,
        "hash": calcular_hash_arquivo(filepath),
        "empresa": {},
        "cargos": [],
        "riscos": [],
        "exames": [],
        "cargo_exames": [],
        "erros_extracao": [],
    }

    # 1. Texto completo com filtro do prestador
    try:
        texto_raw = extrair_texto_pdf(filepath)
        texto = _filtrar_cabecalho_prevenclínica(texto_raw)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair texto: {e}")
        texto = ""

    # 2. Dados da empresa via regex
    resultado["empresa"] = extrair_dados_empresa_por_regex(texto)

    # 3. Cargos, riscos e exames via regex
    try:
        resultado["cargos"] = _extrair_cargos_por_regex(texto)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair cargos: {e}")

    try:
        resultado["riscos"] = _extrair_riscos_por_regex(texto)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair riscos: {e}")

    try:
        resultado["exames"] = _extrair_exames_pcmso_por_regex(texto)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair exames: {e}")

    # 4. Tabelas cargo×exame — parser dedicado das tabelas CONTROLE MÉDICO
    try:
        resultado["cargo_exames"] = extrair_cargo_exames_controle_medico(filepath)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair tabelas CONTROLE MÉDICO: {e}")

    # Fallback genérico: tabelas com colunas cargo|exame explícitas no header
    if not resultado["cargo_exames"]:
        try:
            tabelas = extrair_tabelas_pdf(filepath)
        except Exception as e:
            resultado["erros_extracao"].append(f"Erro ao extrair tabelas: {e}")
            tabelas = []

        for info_tabela in tabelas:
            if _headers_match(info_tabela["headers"], HEADERS_CARGO_EXAMES, threshold=2):
                cargo_exames = _extrair_cargo_exames_de_tabela(info_tabela["dataframe"])
                if cargo_exames:
                    resultado["cargo_exames"].extend(cargo_exames)
                    logger.info(f"Tabela p.{info_tabela['pagina']}: {len(cargo_exames)} mapeamentos cargo-exame")

    resultado["confianca"] = calcular_confianca(resultado, texto)
    if resultado["confianca"]["nivel"] != "ALTA":
        logger.warning(
            f"Confiança {resultado['confianca']['nivel']} "
            f"(score {resultado['confianca']['score_geral']}): "
            f"{'; '.join(resultado['confianca']['avisos'])}"
        )

    logger.info(
        f"Extração concluída: {len(resultado['cargos'])} cargos, "
        f"{len(resultado['riscos'])} riscos, "
        f"{len(resultado['exames'])} exames, "
        f"{len(resultado['cargo_exames'])} mapeamentos cargo-exame"
    )

    return resultado


def salvar_json_extracao(dados: dict, output_path: str | Path) -> None:
    """Salva o resultado da extração em JSON para revisão técnica."""
    output_path = Path(output_path)

    def serializer(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        raise TypeError(f"Tipo não serializável: {type(obj)}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=serializer)

    logger.info(f"JSON de extração salvo em: {output_path}")
