"""
Gerador de mensagens para alertas de exames.
Produz HTML para email e texto formatado para WhatsApp.
"""
from __future__ import annotations

from datetime import date

from src.database.models import Empresa, Exame


def gerar_email_alerta(empresa: Empresa, exames: list[Exame]) -> str:
    """Gera corpo HTML do email de alerta de vencimentos."""
    nome_empresa = empresa.nome_fantasia or empresa.razao_social
    hoje = date.today()

    linhas_tabela = ""
    for ex in sorted(exames, key=lambda e: e.data_proximo_exame):
        dias_restantes = (ex.data_proximo_exame - hoje).days
        cor = "#e74c3c" if dias_restantes <= 10 else "#f39c12"
        linhas_tabela += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee">{ex.colaborador.nome_completo}</td>
            <td style="padding:8px;border-bottom:1px solid #eee">{ex.tipo_exame.nome}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;color:{cor};font-weight:bold">
                {ex.data_proximo_exame.strftime('%d/%m/%Y')}
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;color:{cor}">
                {dias_restantes} dia(s)
            </td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#333">

  <div style="background:linear-gradient(135deg,#2c3e50,#3498db);padding:20px;border-radius:8px 8px 0 0;color:white">
    <h2 style="margin:0">⚠️ Alerta de Exames Ocupacionais</h2>
    <p style="margin:5px 0 0">{nome_empresa}</p>
  </div>

  <div style="background:#fff;border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px">
    <p>Prezado Departamento de SSO,</p>
    <p>Identificamos <strong>{len(exames)} colaborador(es)</strong> com exames ocupacionais
       vencendo nos próximos <strong>10 a 15 dias</strong>:</p>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <thead>
        <tr style="background:#34495e;color:white">
          <th style="padding:10px;text-align:left">Colaborador</th>
          <th style="padding:10px;text-align:left">Exame</th>
          <th style="padding:10px;text-align:left">Vencimento</th>
          <th style="padding:10px;text-align:left">Dias Restantes</th>
        </tr>
      </thead>
      <tbody>{linhas_tabela}</tbody>
    </table>

    <div style="background:#fef9e7;border-left:4px solid #f39c12;padding:12px;margin:16px 0;border-radius:4px">
      <strong>⏰ Ação necessária:</strong> Agende os exames com antecedência para evitar
      irregularidades trabalhistas.
    </div>

    <p>📊 Acesse o dashboard para mais detalhes e exportar relatórios.</p>

    <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
    <p style="font-size:12px;color:#999">
      Este alerta foi gerado automaticamente pelo <strong>PCMSO Alert System</strong>.<br>
      Data de geração: {hoje.strftime('%d/%m/%Y')}
    </p>
  </div>
</body>
</html>"""


def gerar_whatsapp_alerta(empresa: Empresa, exames: list[Exame]) -> str:
    """Gera mensagem texto formatada para WhatsApp (markdown do WhatsApp)."""
    nome_empresa = empresa.nome_fantasia or empresa.razao_social
    hoje = date.today()

    linhas = []
    for ex in sorted(exames, key=lambda e: e.data_proximo_exame):
        dias = (ex.data_proximo_exame - hoje).days
        linhas.append(
            f"• {ex.colaborador.nome_completo} — {ex.tipo_exame.nome} "
            f"({ex.data_proximo_exame.strftime('%d/%m')}, {dias}d)"
        )

    corpo = "\n".join(linhas)

    return (
        f"🚨 *Alerta PCMSO — {nome_empresa}*\n\n"
        f"*{len(exames)} exame(s)* vencendo nos próximos 10-15 dias:\n\n"
        f"{corpo}\n\n"
        f"_Agende com antecedência para evitar irregularidades._\n"
        f"📋 Data: {hoje.strftime('%d/%m/%Y')}"
    )


def gerar_email_relatorio_mensal(empresa: Empresa, dados: dict) -> str:
    """Gera HTML do relatório mensal consolidado."""
    nome_empresa = empresa.nome_fantasia or empresa.razao_social
    mes_ref = dados.get("mes_referencia", "")

    return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#333">

  <div style="background:linear-gradient(135deg,#27ae60,#2ecc71);padding:20px;border-radius:8px 8px 0 0;color:white">
    <h2 style="margin:0">📊 Relatório Mensal PCMSO</h2>
    <p style="margin:5px 0 0">{nome_empresa} — {mes_ref}</p>
  </div>

  <div style="background:#fff;border:1px solid #ddd;border-top:none;padding:20px;border-radius:0 0 8px 8px">
    <h3>Resumo do Mês</h3>
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#f8f9fa">
        <td style="padding:10px;border:1px solid #ddd">Total de Colaboradores Ativos</td>
        <td style="padding:10px;border:1px solid #ddd;font-weight:bold">{dados.get('total_colaboradores', 0)}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #ddd">Exames Realizados no Mês</td>
        <td style="padding:10px;border:1px solid #ddd;color:#27ae60;font-weight:bold">{dados.get('realizados', 0)}</td>
      </tr>
      <tr style="background:#f8f9fa">
        <td style="padding:10px;border:1px solid #ddd">Exames Pendentes</td>
        <td style="padding:10px;border:1px solid #ddd;color:#f39c12;font-weight:bold">{dados.get('pendentes', 0)}</td>
      </tr>
      <tr>
        <td style="padding:10px;border:1px solid #ddd">Exames Vencidos</td>
        <td style="padding:10px;border:1px solid #ddd;color:#e74c3c;font-weight:bold">{dados.get('vencidos', 0)}</td>
      </tr>
      <tr style="background:#f8f9fa">
        <td style="padding:10px;border:1px solid #ddd">Alertas Enviados</td>
        <td style="padding:10px;border:1px solid #ddd">{dados.get('alertas_enviados', 0)}</td>
      </tr>
    </table>

    <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
    <p style="font-size:12px;color:#999">
      Relatório gerado automaticamente pelo <strong>PCMSO Alert System</strong>.
    </p>
  </div>
</body>
</html>"""
