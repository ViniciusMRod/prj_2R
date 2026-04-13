"""
Configuração da Evolution API para envio de mensagens WhatsApp.
"""
import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "pcmso_instance")


def get_evolution_headers() -> dict:
    """Retorna headers padrão para requisições à Evolution API."""
    return {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY,
    }


def get_send_text_url() -> str:
    """URL do endpoint de envio de texto da Evolution API."""
    return f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"


def get_instance_status_url() -> str:
    """URL para verificar status da instância WhatsApp."""
    return f"{EVOLUTION_API_URL}/instance/connectionState/{EVOLUTION_INSTANCE}"
