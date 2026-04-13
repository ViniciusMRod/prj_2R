"""
Validações de dados extraídos de PCMSOs.
CNPJ, CPF, datas e periodicidades com verificação completa de dígitos.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional


PERIODICIDADES_VALIDAS = {6, 12, 24, 36, 48, 60}


# ---------------------------------------------------------------------------
# CNPJ
# ---------------------------------------------------------------------------

def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ incluindo cálculo dos dígitos verificadores.
    Aceita formatos: '12.345.678/0001-90' ou '12345678000190'.
    """
    cnpj_limpo = re.sub(r"[^\d]", "", cnpj)

    if len(cnpj_limpo) != 14:
        return False

    if cnpj_limpo == cnpj_limpo[0] * 14:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj_limpo[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    if int(cnpj_limpo[12]) != digito1:
        return False

    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj_limpo[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    return int(cnpj_limpo[13]) == digito2


def formatar_cnpj(cnpj: str) -> str:
    """Formata CNPJ limpo para XX.XXX.XXX/XXXX-XX."""
    c = re.sub(r"[^\d]", "", cnpj)
    if len(c) == 14:
        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    return cnpj


# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------

def validar_cpf(cpf: str) -> bool:
    """
    Valida CPF incluindo cálculo dos dígitos verificadores.
    Aceita formatos: '123.456.789-09' ou '12345678909'.
    """
    cpf_limpo = re.sub(r"[^\d]", "", cpf)

    if len(cpf_limpo) != 11:
        return False

    if cpf_limpo == cpf_limpo[0] * 11:
        return False

    soma = sum(int(cpf_limpo[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    if int(cpf_limpo[9]) != digito1:
        return False

    soma = sum(int(cpf_limpo[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    return int(cpf_limpo[10]) == digito2


def formatar_cpf(cpf: str) -> str:
    """Formata CPF limpo para XXX.XXX.XXX-XX."""
    c = re.sub(r"[^\d]", "", cpf)
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    return cpf


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------

def validar_datas_exame(data_ultimo: Optional[date], data_proximo: date) -> tuple[bool, str]:
    """
    Valida coerência entre data do último exame e data do próximo.
    Retorna (valido, mensagem_erro).
    """
    if data_ultimo and data_ultimo >= data_proximo:
        return False, f"data_ultimo_exame ({data_ultimo}) deve ser anterior a data_proximo_exame ({data_proximo})"

    if data_proximo < date(2000, 1, 1):
        return False, f"data_proximo_exame ({data_proximo}) parece inválida (antes de 2000)"

    if data_proximo > date(2040, 1, 1):
        return False, f"data_proximo_exame ({data_proximo}) parece inválida (depois de 2040)"

    return True, ""


def validar_periodicidade(meses: int) -> tuple[bool, str]:
    """Valida se a periodicidade está dentro dos valores aceitos."""
    if meses in PERIODICIDADES_VALIDAS:
        return True, ""
    return False, f"Periodicidade {meses} meses não é padrão. Valores aceitos: {sorted(PERIODICIDADES_VALIDAS)}"


# ---------------------------------------------------------------------------
# Validação do JSON extraído do PCMSO
# ---------------------------------------------------------------------------

def validar_dados_extraidos(dados: dict) -> dict:
    """
    Valida o JSON completo extraído do PCMSO.
    Retorna dict com erros e avisos encontrados:
    {
        'valido': bool,
        'erros': [str],
        'avisos': [str],
        'colaboradores_invalidos': [{'nome': str, 'campo': str, 'valor': str}]
    }
    """
    erros: list[str] = []
    avisos: list[str] = []
    colaboradores_invalidos: list[dict] = []

    # Validar empresa
    empresa = dados.get("empresa", {})
    cnpj = empresa.get("cnpj", "")
    if not cnpj:
        erros.append("CNPJ da empresa não encontrado no PCMSO.")
    elif not validar_cnpj(cnpj):
        erros.append(f"CNPJ inválido: {cnpj}")

    if not empresa.get("razao_social"):
        avisos.append("Razão social da empresa não encontrada.")

    # Validar colaboradores
    colaboradores = dados.get("colaboradores", [])
    if not colaboradores:
        erros.append("Nenhum colaborador encontrado no PCMSO.")

    for i, col in enumerate(colaboradores):
        nome = col.get("nome_completo", f"Colaborador #{i+1}")
        cpf = col.get("cpf", "")

        if not cpf:
            colaboradores_invalidos.append({"nome": nome, "campo": "cpf", "valor": "", "erro": "CPF ausente"})
        elif not validar_cpf(cpf):
            colaboradores_invalidos.append({"nome": nome, "campo": "cpf", "valor": cpf, "erro": "CPF inválido"})

    # Validar exames
    exames = dados.get("exames", [])
    if not exames:
        avisos.append("Nenhum exame encontrado no PCMSO.")

    for exame in exames:
        periodo = exame.get("periodicidade_meses")
        if periodo:
            valido, msg = validar_periodicidade(int(periodo))
            if not valido:
                avisos.append(f"Exame '{exame.get('tipo_exame', '?')}': {msg}")

    return {
        "valido": len(erros) == 0,
        "erros": erros,
        "avisos": avisos,
        "colaboradores_invalidos": colaboradores_invalidos,
    }
