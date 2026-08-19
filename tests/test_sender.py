"""Tests para el renderizado de templates y envío de correos."""

from datetime import date
from unittest.mock import ANY, AsyncMock, patch

import pytest

from app.emails.sender import (
    render_reminder,
    send_email,
    send_reminder,
    _format_date,
)


class TestFormatDate:
    def test_known_date(self):
        d = date(2026, 7, 8)
        assert _format_date(d) == "miércoles 8 de julio"

    def test_another_date(self):
        d = date(2026, 1, 1)
        assert _format_date(d) == "jueves 1 de enero"


class TestRenderReminder:
    def test_renders_html_with_activities(self):
        html = render_reminder(
            user_name="Carlos",
            date_str="martes 30 de junio",
            activities=[
                {"name": "Llamada", "partner": "Cliente A",
                 "urgency": "overdue", "label": "Vencida · ayer"},
                {"name": "Reunión", "partner": "Cliente B",
                 "urgency": "today", "label": "Hoy"},
            ],
            opportunities=[],
        )
        assert "<html" in html
        assert "Carlos" in html
        assert "Vencida" in html
        assert "Hoy" in html
        assert "martes 30 de junio" in html

    def test_renders_html_with_opportunities(self):
        html = render_reminder(
            user_name="María",
            date_str="lunes 5 de julio",
            activities=[],
            opportunities=[
                {"name": "Negocio grande", "partner": "Corp SA",
                 "revenue_label": "$48M", "days_until": 3,
                 "probability": 75, "stage": "Negociación", "urgency": "red"},
            ],
        )
        assert "Negocio grande" in html
        assert "$48M" in html
        assert "Negociación" in html

    def test_opportunity_with_associated_activity(self):
        html = render_reminder(
            user_name="Ana",
            date_str="lunes 5 de julio",
            activities=[
                {"id": 1, "name": "Llamada de cierre", "partner": "Corp SA",
                 "urgency": "overdue", "label": "Vencida · ayer", "opp_id": 77},
                {"id": 2, "name": "Telemercadeo", "partner": "Otro",
                 "urgency": "upcoming", "label": "En 3 días", "opp_id": None},
            ],
            opportunities=[
                {"id": 77, "name": "Negocio grande", "partner": "Corp SA",
                 "revenue_label": "$48M", "days_until": 3,
                 "probability": 75, "stage": "Negociación", "urgency": "red",
                 "activities": [
                     {"name": "Llamada de cierre", "urgency": "overdue",
                      "label": "Vencida · ayer"},
                 ]},
            ],
        )
        # La actividad asociada a la oportunidad aparece debajo de ella
        assert "Actividades asociadas" in html
        assert "Llamada de cierre" in html
        # La actividad sin oportunidad va en la sección de "Otras actividades"
        assert "Otras actividades pendientes" in html
        assert "Telemercadeo" in html
        # La integración con Outlook fue retirada: no debe quedar rastro
        assert "outlook" not in html.lower()

    def test_empty_state(self):
        """Correo sin actividades ni oportunidades debe renderizarse sin error."""
        html = render_reminder(
            user_name="Test",
            date_str="lunes 1 de enero",
            activities=[],
            opportunities=[],
        )
        assert html.strip() != ""


class TestSendEmail:
    @patch("app.emails.sender.send_email_via_smtp", new_callable=AsyncMock, return_value=True)
    async def test_success(self, mock_smtp):
        result = await send_email(
            to_email="test@test.com",
            subject="Test",
            html_body="<html></html>",
        )
        assert result is True
        mock_smtp.assert_awaited_once_with("test@test.com", "Test", "<html></html>")

    @patch("app.emails.sender.send_email_via_smtp", new_callable=AsyncMock, return_value=False)
    async def test_smtp_failure(self, mock_smtp):
        result = await send_email(
            to_email="test@test.com",
            subject="Test",
            html_body="<html></html>",
        )
        assert result is False
        mock_smtp.assert_awaited_once()


class TestSendReminder:
    @patch("app.emails.sender.send_email", new_callable=AsyncMock)
    async def test_calls_send_email_with_rendered_html(self, mock_send_email):
        mock_send_email.return_value = True

        result = await send_reminder(
            to_email="vendedor@test.com",
            user_name="Carlos",
            activities=[{"name": "Llamada", "urgency": "overdue", "label": "Vencida"}],
            opportunities=[{"name": "Oppo", "revenue_label": "$10M", "days_until": 5,
                            "probability": 50, "stage": "Propuesta", "urgency": "amber"}],
            ref_date=date(2026, 7, 8),
        )

        assert result is True
        mock_send_email.assert_awaited_once()
        args, _ = mock_send_email.call_args
        assert args[0] == "vendedor@test.com"  # to_email
        assert "🔔" in args[1]  # subject
        assert "Carlos" in args[2]  # html body
