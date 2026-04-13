"""Testes unitários — módulo de comunicações (com mocks)."""
import pytest
from unittest.mock import MagicMock, patch

from src.communications.whatsapp_sender import _formatar_numero


class TestFormatarNumero:
    def test_numero_com_ddi(self):
        assert _formatar_numero("+5511999999999") == "5511999999999"

    def test_numero_sem_ddi(self):
        assert _formatar_numero("11999999999") == "5511999999999"

    def test_numero_formatado(self):
        assert _formatar_numero("(11) 99999-9999") == "5511999999999"

    def test_numero_com_espacos(self):
        assert _formatar_numero("+55 11 99999-9999") == "5511999999999"


class TestEnviarWhatsapp:
    @patch("src.communications.whatsapp_sender.requests.post")
    def test_envio_sucesso(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        from src.communications.whatsapp_sender import enviar_whatsapp
        ok, erro = enviar_whatsapp("+5511999999999", "Teste")
        assert ok is True
        assert erro is None

    @patch("src.communications.whatsapp_sender.requests.post")
    def test_envio_falha_com_retry(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")
        from src.communications.whatsapp_sender import enviar_whatsapp
        with patch("src.communications.whatsapp_sender.time.sleep"):
            ok, erro = enviar_whatsapp("+5511999999999", "Teste")
        assert ok is False
        assert erro is not None

    @patch("src.communications.whatsapp_sender.requests.post")
    def test_retry_3_tentativas(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="Erro")
        from src.communications.whatsapp_sender import MAX_RETRIES, enviar_whatsapp
        with patch("src.communications.whatsapp_sender.time.sleep"):
            enviar_whatsapp("+5511999999999", "Teste")
        assert mock_post.call_count == MAX_RETRIES


class TestGeradorMensagens:
    def _make_empresa(self, nome="Empresa Teste"):
        emp = MagicMock()
        emp.razao_social = nome
        emp.nome_fantasia = nome
        return emp

    def _make_exame(self, colaborador_nome, tipo_nome, dias=12):
        from datetime import date, timedelta
        ex = MagicMock()
        ex.colaborador.nome_completo = colaborador_nome
        ex.tipo_exame.nome = tipo_nome
        ex.data_proximo_exame = date.today() + timedelta(days=dias)
        return ex

    def test_email_contem_nome_empresa(self):
        from src.business_logic.message_generator import gerar_email_alerta
        empresa = self._make_empresa("MetalSP")
        exames = [self._make_exame("João Silva", "Audiometria", 12)]
        html = gerar_email_alerta(empresa, exames)
        assert "MetalSP" in html
        assert "João Silva" in html
        assert "Audiometria" in html

    def test_whatsapp_formato_markdown(self):
        from src.business_logic.message_generator import gerar_whatsapp_alerta
        empresa = self._make_empresa("MetalSP")
        exames = [self._make_exame("Maria Santos", "Hemograma", 10)]
        msg = gerar_whatsapp_alerta(empresa, exames)
        assert "*" in msg  # markdown bold
        assert "MetalSP" in msg
        assert "Maria Santos" in msg

    def test_mensagem_lista_todos_colaboradores(self):
        from src.business_logic.message_generator import gerar_email_alerta
        empresa = self._make_empresa()
        nomes = ["Colaborador A", "Colaborador B", "Colaborador C"]
        exames = [self._make_exame(n, "Audiometria", 12) for n in nomes]
        html = gerar_email_alerta(empresa, exames)
        for nome in nomes:
            assert nome in html
