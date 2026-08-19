"""Tests de integración para los endpoints FastAPI.

Usa el test_client de conftest.py que sobreescribe la DB y mockea OdooClient.
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import ReminderLog


class TestHealth:
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["tz"] == "America/Bogota"


class TestTestReminder:
    async def test_test_reminder_with_body(self, client: AsyncClient):
        with patch("app.routers.reminders.get_sales_users", return_value=[]):
            resp = await client.post(
                "/api/test-reminder",
                json={"to_email": "test@example.com"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("error") == "No sales users with email found"

    async def test_test_reminder_default_email(self, client: AsyncClient):
        with patch("app.routers.reminders.get_sales_users", return_value=[]):
            resp = await client.post(
                "/api/test-reminder",
                json={},
            )
            assert resp.status_code == 200
            assert resp.json().get("error") is not None


class TestTriggerReminders:
    async def test_trigger_empty_success(self, client: AsyncClient, db_session: AsyncSession):
        """Cuando no hay usuarios con actividades, el trigger debe responder OK
        con total=0."""
        with patch("app.routers.reminders.run_daily_reminders", new_callable=MockAsync) as mock_run:
            mock_run.return_value = []
            resp = await client.post("/api/trigger-reminders")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["sent"] == 0
            assert data["failed"] == 0

    async def test_trigger_with_results(self, client: AsyncClient):
        """Simula una corrida con 2 usuarios."""
        fake_results = [
            {"user_id": 6, "user_email": "a@b.com", "activities_count": 2,
             "opportunities_count": 1, "status": "sent"},
            {"user_id": 7, "user_email": "c@d.com", "activities_count": 0,
             "opportunities_count": 0, "status": "failed"},
        ]
        with patch("app.routers.reminders.run_daily_reminders", new_callable=MockAsync) as mock_run:
            mock_run.return_value = fake_results
            resp = await client.post("/api/trigger-reminders")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert data["sent"] == 1
            assert data["failed"] == 1

    async def test_trigger_internal_error(self, client: AsyncClient):
        with patch("app.routers.reminders.run_daily_reminders", new_callable=MockAsync) as mock_run:
            mock_run.side_effect = ValueError("Something went wrong")
            resp = await client.post("/api/trigger-reminders")
            assert resp.status_code == 500


class MockAsync:
    """Crea un callable async que devuelve o levanta lo que se le indique."""

    def __init__(self, return_value=None, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect

    async def __call__(self, *args, **kwargs):
        if self.side_effect:
            raise self.side_effect
        return self.return_value


class TestLogs:
    async def test_list_logs_empty(self, client: AsyncClient):
        resp = await client.get("/api/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_logs_with_data(self, client: AsyncClient, db_session: AsyncSession):
        db_session.add(ReminderLog(
            user_id=6, user_email="a@b.com", user_name="A",
            activities_count=3, opportunities_count=1, status="sent",
        ))
        await db_session.commit()

        resp = await client.get("/api/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["user_email"] == "a@b.com"
        assert data[0]["status"] == "sent"

    async def test_logs_stats(self, client: AsyncClient, db_session: AsyncSession):
        for i in range(5):
            db_session.add(ReminderLog(
                user_id=i, user_email=f"u{i}@b.com", user_name=f"U{i}",
                activities_count=1, opportunities_count=0, status="sent",
            ))
        db_session.add(ReminderLog(
            user_id=99, user_email="fail@b.com", user_name="Fail",
            activities_count=1, opportunities_count=0, status="failed",
        ))
        await db_session.commit()

        resp = await client.get("/api/logs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sent"] == 5
        assert data["total_failed"] == 1
        assert data["total_errors"] == 0
        assert data["unique_users"] == 6
