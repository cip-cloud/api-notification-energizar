"""Tests para la lógica del cron diario (cron/daily.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cron.daily import _revenue_label, run_daily_reminders, setup_scheduler


class TestRevenueLabel:
    def test_millions(self):
        assert _revenue_label(48_000_000) == "$48M"
        assert _revenue_label(1_000_000) == "$1M"

    def test_thousands(self):
        assert _revenue_label(25_000_000) == "$25M"
        assert _revenue_label(500_000) == "$500,000"
        assert _revenue_label(0) == "$0"
        assert _revenue_label(999_999) == "$999,999"


class TestRunDailyReminders:
    @patch("app.cron.daily.get_sales_users")
    @patch("app.cron.daily.get_pending_activities")
    @patch("app.cron.daily.get_opportunities")
    @patch("app.cron.daily.send_reminder", new_callable=AsyncMock)
    @patch("app.cron.daily.ReminderLog")
    async def test_empty_users(self, mock_log, mock_send, mock_opps,
                              mock_acts, mock_users):
        """Sin usuarios, el cron responde OK con lista vacía."""
        mock_users.return_value = []
        mock_acts.return_value = {}
        mock_opps.return_value = {}

        result = await run_daily_reminders()
        assert result == []

    @patch("app.cron.daily.get_sales_users")
    @patch("app.cron.daily.get_pending_activities")
    @patch("app.cron.daily.get_opportunities")
    @patch("app.cron.daily.send_reminder", new_callable=AsyncMock)
    @patch("app.cron.daily.load_notified_state", new_callable=AsyncMock)
    @patch("app.cron.daily.record_opportunities", new_callable=AsyncMock)
    @patch("app.cron.daily.record_activities", new_callable=AsyncMock)
    @patch("app.cron.daily.AsyncSession")
    async def test_processes_users(self, mock_session, mock_record_acts,
                                   mock_record_opps, mock_state, mock_send,
                                   mock_opps, mock_acts, mock_users):
        user = type("User", (), {"id": 6, "name": "Test", "email": "t@t.com"})()
        mock_users.return_value = [user]
        # Actividad mock mínima para que el cron no haga continue
        act = MagicMock(id=10, summary="Call", activity_type_name="Call", partner_name=None,
                        urgency="today", label="Hoy", res_model="crm.lead", res_id=1)
        mock_acts.return_value = {6: [act]}
        opp = MagicMock(id=1, name="Deal", partner_name="Client", expected_revenue=10_000,
                        days_until_deadline=5, probability=50, stage_id=3,
                        stage_name="Negotiation", urgency="amber")
        mock_opps.return_value = {6: [opp]}
        mock_send.return_value = True
        mock_state.return_value = ({}, set())
        mock_ctx = AsyncMock()
        mock_ctx.add = MagicMock()
        mock_ctx.commit = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_ctx

        result = await run_daily_reminders()
        assert len(result) == 1
        assert result[0]["status"] == "sent"
        mock_record_opps.assert_awaited_once()
        mock_record_acts.assert_awaited_once()


class TestSetupScheduler:
    def test_adds_cron_job(self):
        """setup_scheduler() debe agregar un job al scheduler."""
        from app.cron.daily import scheduler
        scheduler.remove_all_jobs()
        assert len(scheduler.get_jobs()) == 0

        setup_scheduler()
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "daily_reminders"
        # Verifica que corra todos los días (sin restricción day_of_week)
        fields = {f.name: str(f) for f in jobs[0].trigger.fields}
        assert fields.get("day_of_week", "*") == "*"
