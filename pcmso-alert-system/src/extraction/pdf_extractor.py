"""
Extrator de dados de PDFs PCMSO.
Baseado na skill document-data-extraction: combina pdfplumber (tabelas) +
PyPDF2 (texto) + regex (campos estruturados) em pipeline híbrido.
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
# Padrões Regex para documentos PCMSO brasileiros
# ---------------------------------------------------------------------------

PCMSO_PATTERNS = {
    "cnpj": r"CNPJ[:\s]*(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2})",
    "razao_social": r"(?:Razão Social|RAZÃO SOCIAL|Empresa|EMPRESA)[:\s]+([A-Za-zÀ-ú0-9\s\.\,\-\_&]+?)(?:\n|CNPJ|CPF)",
    "nome_fantasia": r"(?:Nome Fantasia|NOME FANTASIA)[:\s]+([A-Za-zÀ-ú0-9\s\.\,\-\_&]+?)(?:\n|CNPJ)",
    "ano_referencia": r"(?:Ano de Referência|ANO|Exercício)[:\s]*(\d{4})",
    "email_sso": r"(?:E-mail|Email|e-mail)[:\s]*([\w\.\-]+@[\w\.\-]+\.\w+)",
    "telefone": r"(?:Telefone|Tel|Fone)[:\s]*([\(\d\)\s\-\+]{10,20})",
    "cpf_col": r"(?:CPF)[:\s]*(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?\d{2})",
    "data_br": r"(\d{2}/\d{2}/\d{4})",
}

# Headers comuns em tabelas de PCMSO
HEADERS_COLABORADORES = [
    "nome", "cpf", "cargo", "setor", "função", "admissão", "admissao",
    "colaborador", "funcionário", "funcionario",
]

HEADERS_EXAMES = [
    "exame", "tipo", "periodicidade", "último", "ultimo", "próximo", "proximo",
    "vencimento", "data", "realização", "realizacao",
]

TIPOS_EXAMES_CONHECIDOS = [
    "audiometria", "acuidade visual", "hemograma", "espirometria",
    "eletrocardiograma", "ecg", "raio-x", "radiografia", "glicemia",
    "colesterol", "triglicérides", "triglicerides", "urina", "parasitológico",
    "avaliação clínica", "avaliacao clinica", "exame médico", "exame medico",
    "eletroencefalograma", "eeg", "toxicológico", "toxicologico",
    "bioquímica", "bioquimica", "creatinina", "tgo", "tgp",
]


# ---------------------------------------------------------------------------
# Análise estrutural do PDF
# ---------------------------------------------------------------------------

def analisar_pdf(filepath: str | Path) -> dict:
    """
    Analisa a estrutura do PDF: número de páginas e quantidade de tabelas.
    Baseado em analyze_pdf() da skill document-data-extraction.
    """
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
    Baseado em extract_tables_from_pdf() da skill document-data-extraction.
    Retorna lista de dicts com página, número da tabela e DataFrame.
    """
    tabelas = []
    with pdfplumber.open(filepath) as pdf:
        for num_pagina, pagina in enumerate(pdf.pages, 1):
            tables = pagina.extract_tables()
            for num_tabela, table in enumerate(tables, 1):
                if table and len(table) > 1:
                    # Primeira linha como header
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
# Identificação de tabela de colaboradores / exames
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


def _extrair_colaboradores_de_tabela(df: pd.DataFrame) -> list[dict]:
    """Tenta extrair dados de colaboradores de um DataFrame."""
    colaboradores = []
    cols_lower = {c.lower(): c for c in df.columns}

    col_nome = next((cols_lower[k] for k in cols_lower if "nome" in k or "colaborador" in k or "funcionário" in k), None)
    col_cpf = next((cols_lower[k] for k in cols_lower if "cpf" in k), None)
    col_cargo = next((cols_lower[k] for k in cols_lower if "cargo" in k or "função" in k or "funcao" in k), None)
    col_setor = next((cols_lower[k] for k in cols_lower if "setor" in k or "área" in k or "area" in k), None)
    col_admissao = next((cols_lower[k] for k in cols_lower if "admiss" in k), None)

    for _, row in df.iterrows():
        nome = str(row[col_nome]).strip() if col_nome and pd.notna(row[col_nome]) else ""
        cpf = str(row[col_cpf]).strip() if col_cpf and pd.notna(row[col_cpf]) else ""

        if not nome or nome.lower() in ("nan", "none", ""):
            continue

        col = {
            "nome_completo": nome,
            "cpf": re.sub(r"[^\d]", "", cpf),
            "cargo": str(row[col_cargo]).strip() if col_cargo and pd.notna(row[col_cargo]) else "",
            "setor": str(row[col_setor]).strip() if col_setor and pd.notna(row[col_setor]) else "",
            "data_admissao": _parse_data_br(str(row[col_admissao])) if col_admissao and pd.notna(row[col_admissao]) else None,
        }
        colaboradores.append(col)

    return colaboradores


def _extrair_exames_de_tabela(df: pd.DataFrame) -> list[dict]:
    """Tenta extrair dados de exames de um DataFrame."""
    exames = []
    cols_lower = {c.lower(): c for c in df.columns}

    col_colaborador = next((cols_lower[k] for k in cols_lower if "nome" in k or "colaborador" in k), None)
    col_tipo = next((cols_lower[k] for k in cols_lower if "exame" in k or "tipo" in k), None)
    col_period = next((cols_lower[k] for k in cols_lower if "period" in k), None)
    col_ultimo = next((cols_lower[k] for k in cols_lower if "último" in k or "ultimo" in k or "realiz" in k), None)
    col_proximo = next((cols_lower[k] for k in cols_lower if "próximo" in k or "proximo" in k or "vencim" in k), None)

    for _, row in df.iterrows():
        tipo = str(row[col_tipo]).strip() if col_tipo and pd.notna(row[col_tipo]) else ""
        if not tipo or tipo.lower() in ("nan", "none", ""):
            continue

        exame = {
            "colaborador_nome": str(row[col_colaborador]).strip() if col_colaborador and pd.notna(row[col_colaborador]) else "",
            "tipo_exame": tipo,
            "periodicidade_meses": None,
            "data_ultimo_exame": None,
            "data_proximo_exame": None,
        }

        if col_period and pd.notna(row[col_period]):
            nums = re.findall(r"\d+", str(row[col_period]))
            if nums:
                exame["periodicidade_meses"] = int(nums[0])

        if col_ultimo and pd.notna(row[col_ultimo]):
            exame["data_ultimo_exame"] = _parse_data_br(str(row[col_ultimo]))

        if col_proximo and pd.notna(row[col_proximo]):
            exame["data_proximo_exame"] = _parse_data_br(str(row[col_proximo]))

        exames.append(exame)

    return exames


def _extrair_cargo_exames_de_tabela(df: pd.DataFrame) -> list[dict]:
    """Extrai mapeamento cargo/risco → exames da tabela de riscos do PCMSO."""
    cargo_exames = []
    cols_lower = {c.lower(): c for c in df.columns}

    col_cargo = next((cols_lower[k] for k in cols_lower if "cargo" in k or "função" in k), None)
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
# Extração por regex (texto livre)
# ---------------------------------------------------------------------------

def extrair_dados_empresa_por_regex(texto: str) -> dict:
    """Extrai dados da empresa usando padrões regex no texto do PDF."""
    dados: dict = {}

    cnpj_match = re.search(PCMSO_PATTERNS["cnpj"], texto, re.IGNORECASE)
    if cnpj_match:
        dados["cnpj"] = formatar_cnpj(cnpj_match.group(1))

    razao_match = re.search(PCMSO_PATTERNS["razao_social"], texto, re.IGNORECASE | re.DOTALL)
    if razao_match:
        dados["razao_social"] = razao_match.group(1).strip()

    ano_match = re.search(PCMSO_PATTERNS["ano_referencia"], texto, re.IGNORECASE)
    if ano_match:
        dados["ano_referencia"] = int(ano_match.group(1))

    email_match = re.search(PCMSO_PATTERNS["email_sso"], texto, re.IGNORECASE)
    if email_match:
        dados["email_sso"] = email_match.group(1).strip()

    return dados


# ---------------------------------------------------------------------------
# Pipeline principal de extração
# ---------------------------------------------------------------------------

def extrair_pcmso(filepath: str | Path) -> dict:
    """
    Pipeline completo de extração de dados de um PCMSO PDF.

    Estratégia híbrida (baseada na skill document-data-extraction):
    1. Analisa estrutura do PDF
    2. Extrai texto completo (PyPDF2) + tabelas (pdfplumber)
    3. Aplica regex para dados da empresa
    4. Identifica tabelas de colaboradores e exames
    5. Retorna JSON estruturado

    Retorna:
    {
        "arquivo": str,
        "hash": str,
        "empresa": {...},
        "colaboradores": [...],
        "exames": [...],
        "cargo_exames": [...],
        "erros_extracao": [str]
    }
    """
    filepath = Path(filepath)
    logger.info(f"Iniciando extração: {filepath.name}")

    resultado = {
        "arquivo": str(filepath),
        "hash": calcular_hash_arquivo(filepath),
        "empresa": {},
        "colaboradores": [],
        "exames": [],
        "cargo_exames": [],
        "erros_extracao": [],
    }

    # 1. Analisar estrutura
    info = analisar_pdf(filepath)

    # 2. Texto completo
    try:
        texto = extrair_texto_pdf(filepath)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair texto: {e}")
        texto = ""

    # 3. Dados da empresa via regex
    resultado["empresa"] = extrair_dados_empresa_por_regex(texto)

    # 4. Tabelas
    try:
        tabelas = extrair_tabelas_pdf(filepath)
    except Exception as e:
        resultado["erros_extracao"].append(f"Erro ao extrair tabelas: {e}")
        tabelas = []

    for info_tabela in tabelas:
        df = info_tabela["dataframe"]
        headers = info_tabela["headers"]

        # Tentar identificar tipo de tabela
        if _headers_match(headers, HEADERS_COLABORADORES, threshold=2):
            colaboradores = _extrair_colaboradores_de_tabela(df)
            if colaboradores:
                resultado["colaboradores"].extend(colaboradores)
                logger.info(f"Tabela p.{info_tabela['pagina']}: {len(colaboradores)} colaboradores extraídos")

        elif _headers_match(headers, HEADERS_EXAMES, threshold=2):
            exames = _extrair_exames_de_tabela(df)
            if exames:
                resultado["exames"].extend(exames)
                logger.info(f"Tabela p.{info_tabela['pagina']}: {len(exames)} exames extraídos")

            # Pode ser também tabela de cargo × exames
            cargo_exames = _extrair_cargo_exames_de_tabela(df)
            if cargo_exames:
                resultado["cargo_exames"].extend(cargo_exames)
                logger.info(f"Tabela p.{info_tabela['pagina']}: {len(cargo_exames)} mapeamentos cargo-exame extraídos")

    logger.info(
        f"Extração concluída: {len(resultado['colaboradores'])} colaboradores, "
        f"{len(resultado['exames'])} exames, "
        f"{len(resultado['cargo_exames'])} mapeamentos cargo-exame"
    )

    return resultado


def salvar_json_extracao(dados: dict, output_path: str | Path) -> None:
    """Salva o resultado da extração em JSON para revisão técnica."""
    output_path = Path(output_path)

    # Converter dates para string antes de serializar
    def serializer(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        raise TypeError(f"Tipo não serializável: {type(obj)}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=serializer)

    logger.info(f"JSON de extração salvo em: {output_path}")
