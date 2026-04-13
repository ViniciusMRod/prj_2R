"""
Configuração da Gmail API (OAuth2).
Gerencia credenciais e token de acesso.
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "config/gmail_credentials.json")
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "config/gmail_token.json")
GMAIL_SENDER_EMAIL = os.getenv("GMAIL_SENDER_EMAIL", "alertas@seudominio.com.br")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service():
    """
    Retorna o serviço autenticado da Gmail API.
    Na primeira execução, abre browser para autorização OAuth2.
    Nas execuções seguintes, usa o token salvo em GMAIL_TOKEN_FILE.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None

    token_path = Path(GMAIL_TOKEN_FILE)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("Token Gmail renovado automaticamente.")
        else:
            if not Path(GMAIL_CREDENTIALS_FILE).exists():
                raise FileNotFoundError(
                    f"Arquivo de credenciais Gmail não encontrado: {GMAIL_CREDENTIALS_FILE}\n"
                    "Baixe o credentials.json no Google Cloud Console e salve neste caminho."
                )
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Autorização Gmail concluída.")

        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
