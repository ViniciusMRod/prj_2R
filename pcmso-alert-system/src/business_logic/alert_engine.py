"""
Motor de alertas diários — identifica exames vencendo em 10-15 dias
e dispara notificações via email e WhatsApp por empresa.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import AlertaEnviado, CanalAlerta, Exame, StatusEnvio
from src.database.queries import (
    agrupar_por_empresa,
    alerta_ja_enviado_hoje,
    get_empresa_by_id,
    marcar_exames_vencidos,
    query_exames_por_vencimento,
)

logger = logging.getLogger(__name__)

JANELA_INICIO_DIAS = 10
JANELA_FIM_DIAS    = 15


def processar_alertas_diarios(db: Session) -> dict:
    """
    Executado todo dia às 05:00 via n8n.

    1. Marca exames vencidos
    2. Busca exames vencendo em D+10 a D+15
    3. Agrupa por empresa
    4. Envia email + WhatsApp para cada empresa (sem duplicar no mesmo dia)
    5. Registra histórico

    Retorna dict com resumo do processamento.
    """
    from src.business_logic.message_generator import gerar_email_alerta, gerar_whatsapp_alerta
    from src.communications.gmail_sender import enviar_email
    from src.communications.whatsapp_sender import enviar_whatsapp

    logger.info("=== Iniciando processamento de alertas diários ===")

    hoje = date.today()
    janela_inicio = hoje + timedelta(days=JANELA_INICIO_DIAS)
    janela_fim    = hoje + timedelta(days=JANELA_FIM_DIAS)

    # 1. Atualizar status de vencidos
    qtd_vencidos = marcar_exames_vencidos(db)

    # 2. Buscar exames na janela
    exames = query_exames_por_vencimento(db, janela_inicio, janela_fim)
    logger.info(f"{len(exames)} exame(s) vencendo entre {janela_inicio} e {janela_fim}")

    if not exames:
        return {
            "ok": True,
            "data": hoje.isoformat(),
            "exames_encontrados": 0,
            "alertas_enviados": 0,
            "alertas_falhos": 0,
            "exames_vencidos_atualizados": qtd_vencidos,
        }

    # 3. Agrupar por empresa
    por_empresa = agrupar_por_empresa(exames)
    alertas_enviados = 0
    alertas_falhos = 0

    for empresa_id, lista_exames in por_empresa.items():
        empresa = get_empresa_by_id(db, empresa_id)
        if not empresa:
            continue

        logger.info(f"Processando empresa: {empresa.razao_social} ({len(lista_exames)} exame(s))")

        # --- EMAIL ---
        if empresa.email_sso and not alerta_ja_enviado_hoje(db, empresa_id, CanalAlerta.EMAIL):
            mensagem_email = gerar_email_alerta(empresa, lista_exames)
            assunto = f"⚠️ [{empresa.nome_fantasia or empresa.razao_social}] — {len(lista_exames)} exame(s) vencendo em 10-15 dias"

            sucesso_email, erro_email = enviar_email(empresa.email_sso, assunto, mensagem_email)
            _registrar_alerta(
                db, empresa_id, lista_exames, CanalAlerta.EMAIL,
                mensagem_email, sucesso_email, erro_email,
            )
            if sucesso_email:
                alertas_enviados += 1
            else:
                alertas_falhos += 1
                logger.error(f"Falha no email para {empresa.email_sso}: {erro_email}")
        else:
            logger.info(f"Email já enviado hoje para empresa_id={empresa_id} — pulando.")

        # --- WHATSAPP ---
        if empresa.whatsapp_sso and not alerta_ja_enviado_hoje(db, empresa_id, CanalAlerta.WHATSAPP):
            mensagem_wpp = gerar_whatsapp_alerta(empresa, lista_exames)

            sucesso_wpp, erro_wpp = enviar_whatsapp(empresa.whatsapp_sso, mensagem_wpp)
            _registrar_alerta(
                db, empresa_id, lista_exames, CanalAlerta.WHATSAPP,
                mensagem_wpp, sucesso_wpp, erro_wpp,
            )
            if sucesso_wpp:
                alertas_enviados += 1
            else:
                alertas_falhos += 1
                logger.error(f"Falha no WhatsApp para {empresa.whatsapp_sso}: {erro_wpp}")
        else:
            logger.info(f"WhatsApp já enviado hoje para empresa_id={empresa_id} — pulando.")

    logger.info(
        f"=== Alertas concluídos: {alertas_enviados} enviados, {alertas_falhos} falhos ==="
    )

    return {
        "ok": True,
        "data": hoje.isoformat(),
        "exames_encontrados": len(exames),
        "empresas_notificadas": len(por_empresa),
        "alertas_enviados": alertas_enviados,
        "alertas_falhos": alertas_falhos,
        "exames_vencidos_atualizados": qtd_vencidos,
    }


def _registrar_alerta(
    db: Session,
    empresa_id: int,
    exames: list[Exame],
    canal: CanalAlerta,
    mensagem: str,
    sucesso: bool,
    erro_detalhe: Optional[str],
) -> None:
    """Registra um alerta enviado no histórico (um registro por empresa/canal/dia)."""
    alerta = AlertaEnviado(
        exame_id=exames[0].id if exames else None,
        empresa_id=empresa_id,
        canal=canal,
        mensagem=mensagem,
        status_envio=StatusEnvio.ENVIADO if sucesso else StatusEnvio.FALHOU,
        erro_detalhe=erro_detalhe,
    )
    db.add(alerta)
    db.commit()
