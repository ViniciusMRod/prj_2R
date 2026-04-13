"""
Envio de emails via Gmail API (OAuth2).
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GMAIL_SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "alertas@seudominio.com.br")


def enviar_email(
    destinatario: str,
    assunto: str,
    html_body: str,
    anexos: Optional[list[Optional[str]]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Envia email via Gmail API.

    Returns:
        (sucesso: bool, erro: Optional[str])
    """
    try:
        from config.gmail_config import get_gmail_service
        service = get_gmail_service()

        msg = MIMEMultipart("mixed")
        msg["to"]      = destinatario
        msg["from"]    = GMAIL_SENDER_EMAIL
        msg["subject"] = assunto

        # Corpo HTML
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Anexos opcionais
        if anexos:
            for path_str in anexos:
                if not path_str:
                    continue
                path = Path(path_str)
                if not path.exists():
                    logger.warning(f"Anexo não encontrado: {path_str}")
                    continue
                mime_type, _ = mimetypes.guess_type(str(path))
                maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
                with open(path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=path.name)
                    part["Content-Disposition"] = f'attachment; filename="{path.name}"'
                    msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        logger.info(f"Email enviado para {destinatario}: {assunto[:60]}")
        return True, None

    except Exception as e:
        logger.error(f"Falha ao enviar email para {destinatario}: {e}")
        return False, str(e)


def enviar_emails_lote(
    destinatarios: list[str],
    assunto: str,
    html_body: str,
) -> dict[str, bool]:
    """Envia o mesmo email para múltiplos destinatários. Retorna {email: sucesso}."""
    resultados = {}
    for dest in destinatarios:
        sucesso, _ = enviar_email(dest, assunto, html_body)
        resultados[dest] = sucesso
    return resultados
