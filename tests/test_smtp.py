"""Tests para el envío de correos por SMTP."""

from unittest.mock import MagicMock, patch

from app.emails.smtp import _build_message, send_email_via_smtp


class TestBuildMessage:
    def test_headers_and_html_alternative(self):
        msg = _build_message("vendedor@test.com", "Asunto", "<html><b>hola</b></html>")
        assert msg["To"] == "vendedor@test.com"
        assert msg["Subject"] == "Asunto"
        assert msg["From"]  # remitente tomado de reminder_sender
        html_part = msg.get_body(preferencelist=("html",))
        assert html_part is not None
        assert "hola" in html_part.get_content()


class TestSendEmailViaSmtp:
    async def test_not_configured_returns_false(self):
        with patch("app.emails.smtp.settings") as mock_settings:
            mock_settings.smtp_host = None
            result = await send_email_via_smtp("a@test.com", "S", "<html></html>")
        assert result is False

    @patch("app.emails.smtp.smtplib.SMTP")
    async def test_success_with_starttls_and_login(self, mock_smtp_cls):
        server = MagicMock()
        mock_smtp_cls.return_value = server
        server.__enter__ = MagicMock(return_value=server)
        server.__exit__ = MagicMock(return_value=False)

        with patch("app.emails.smtp.settings") as mock_settings:
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_ssl = False
            mock_settings.smtp_starttls = True
            mock_settings.smtp_user = "user@test.com"
            mock_settings.smtp_password = "clave"
            mock_settings.reminder_sender = "CRM <crm@test.com>"
            result = await send_email_via_smtp("a@test.com", "S", "<html></html>")

        assert result is True
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("user@test.com", "clave")
        server.send_message.assert_called_once()

    @patch("app.emails.smtp.smtplib.SMTP")
    async def test_connection_error_returns_false(self, mock_smtp_cls):
        mock_smtp_cls.side_effect = OSError("connection refused")
        with patch("app.emails.smtp.settings") as mock_settings:
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_ssl = False
            result = await send_email_via_smtp("a@test.com", "S", "<html></html>")
        assert result is False
