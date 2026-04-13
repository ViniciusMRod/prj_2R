"""
Envio de mensagens WhatsApp via Evolution API.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config.whatsapp_config import (
    get_evolution_headers,
    get_instance_status_url,
    get_send_text_url,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos


def _formatar_numero(numero: str) -> str:
    """
    Normaliza número de telefone para formato Evolution API.
    Aceita: +55 11 99999-9999, 5511999999999, (11) 99999-9999
    Retorna: '5511999999999' (apenas dígitos, com DDI)
    """
    import re
    digits = re.sub(r"\D", "", numero)
    if not digits.startswith("55"):
        digits = "55" + digits
    return digits


def verificar_instancia() -> tuple[bool, str]:
    """Verifica se a instância WhatsApp está conectada."""
    try:
        resp = requests.get(
            get_instance_status_url(),
            headers=get_evolution_headers(),
            timeout=10,
        )
        data = resp.json()
        state = data.get("instance", {}).get("state", "unknown")
        conectado = state == "open"
        return conectado, state
    except Exception as e:
        return False, str(e)


def enviar_whatsapp(
    numero: str,
    mensagem: str,
) -> tuple[bool, Optional[str]]:
    """
    Envia mensagem de texto via Evolution API com retry automático.

    Returns:
        (sucesso: bool, erro: Optional[str])
    """
    numero_fmt = _formatar_numero(numero)
    payload = {
        "number": numero_fmt,
        "text": mensagem,
    }

    ultimo_erro: Optional[str] = None

    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                get_send_text_url(),
                headers=get_evolution_headers(),
                json=payload,
                timeout=15,
            )

            if resp.status_code in (200, 201):
                logger.info(f"WhatsApp enviado para {numero_fmt} (tentativa {tentativa})")
                return True, None

            ultimo_erro = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning(f"Tentativa {tentativa}/{MAX_RETRIES} falhou: {ultimo_erro}")

        except requests.Timeout:
            ultimo_erro = "Timeout na requisição"
            logger.warning(f"Tentativa {tentativa}/{MAX_RETRIES} — timeout")
        except Exception as e:
            ultimo_erro = str(e)
            logger.warning(f"Tentativa {tentativa}/{MAX_RETRIES} — erro: {e}")

        if tentativa < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    logger.error(f"Falha ao enviar WhatsApp para {numero_fmt} após {MAX_RETRIES} tentativas: {ultimo_erro}")
    return False, ultimo_erro
