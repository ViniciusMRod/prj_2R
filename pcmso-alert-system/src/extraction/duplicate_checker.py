"""
Detector de PCMSOs duplicados usando hash MD5/SHA256.
"""
from __future__ import annotations

import hashlib
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import PcmsoVersao

logger = logging.getLogger(__name__)


class ResultadoDuplicata(str, Enum):
    DUPLICATA_EXATA = "duplicata_exata"
    NOVA_VERSAO = "nova_versao"
    NOVO_ARQUIVO = "novo_arquivo"


def calcular_hash_arquivo(filepath: str | Path) -> str:
    """Calcula SHA256 do arquivo para detecção de duplicatas."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def verificar_duplicata(
    db: Session,
    hash_arquivo: str,
    empresa_id: int,
    ano_referencia: int,
) -> tuple[ResultadoDuplicata, Optional[PcmsoVersao], str]:
    """
    Verifica se o arquivo já existe no banco.

    Retorna:
        (resultado, versao_existente, mensagem)

    Casos:
        - DUPLICATA_EXATA: mesmo hash → rejeitar
        - NOVA_VERSAO: mesma empresa + mesmo ano, hash diferente → perguntar ao técnico
        - NOVO_ARQUIVO: nunca visto → prosseguir normalmente
    """
    from sqlalchemy import select, and_

    # 1. Verificar hash exato
    versao_por_hash = db.scalar(
        select(PcmsoVersao).where(PcmsoVersao.hash_arquivo == hash_arquivo)
    )
    if versao_por_hash:
        msg = (
            f"PCMSO DUPLICADO: arquivo idêntico já foi carregado em "
            f"{versao_por_hash.data_upload.strftime('%d/%m/%Y')} "
            f"(empresa_id={versao_por_hash.empresa_id}, "
            f"ano={versao_por_hash.ano_referencia}, v{versao_por_hash.versao})."
        )
        logger.warning(msg)
        return ResultadoDuplicata.DUPLICATA_EXATA, versao_por_hash, msg

    # 2. Verificar empresa + ano (hash diferente = nova versão)
    versoes_mesmo_ano = list(db.scalars(
        select(PcmsoVersao).where(
            and_(
                PcmsoVersao.empresa_id == empresa_id,
                PcmsoVersao.ano_referencia == ano_referencia,
            )
        ).order_by(PcmsoVersao.versao.desc())
    ))

    if versoes_mesmo_ano:
        ultima = versoes_mesmo_ano[0]
        msg = (
            f"NOVA VERSÃO DETECTADA: já existe PCMSO para empresa_id={empresa_id}, "
            f"ano={ano_referencia} (versão atual: v{ultima.versao}). "
            f"Este arquivo será registrado como v{ultima.versao + 1}."
        )
        logger.info(msg)
        return ResultadoDuplicata.NOVA_VERSAO, ultima, msg

    return ResultadoDuplicata.NOVO_ARQUIVO, None, "Arquivo novo — nenhuma duplicata encontrada."


def registrar_versao(
    db: Session,
    empresa_id: int,
    ano_referencia: int,
    arquivo_path: str,
    hash_arquivo: str,
) -> PcmsoVersao:
    """
    Registra uma nova versão de PCMSO no banco.
    Calcula automaticamente o número da versão.
    """
    from sqlalchemy import select, and_, func

    versao_atual = db.scalar(
        select(func.max(PcmsoVersao.versao)).where(
            and_(
                PcmsoVersao.empresa_id == empresa_id,
                PcmsoVersao.ano_referencia == ano_referencia,
            )
        )
    ) or 0

    nova_versao = PcmsoVersao(
        empresa_id=empresa_id,
        versao=versao_atual + 1,
        ano_referencia=ano_referencia,
        arquivo_path=arquivo_path,
        hash_arquivo=hash_arquivo,
    )
    db.add(nova_versao)
    db.commit()
    db.refresh(nova_versao)

    logger.info(
        f"Versão registrada: empresa_id={empresa_id} ano={ano_referencia} "
        f"v{nova_versao.versao} hash={hash_arquivo[:12]}..."
    )
    return nova_versao
