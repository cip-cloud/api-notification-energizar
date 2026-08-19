"""Tests unitarios para las dataclasses y sus propiedades calculadas."""

from datetime import date

from app.odoo.models import Activity, Opportunity


class TestActivity:
    def test_urgency_overdue(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 1),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.urgency == "overdue"

    def test_urgency_today(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 5),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.urgency == "today"

    def test_urgency_upcoming(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 10),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.urgency == "upcoming"

    def test_label_overdue_yesterday(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 4),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.label == "Vencida · ayer"

    def test_label_overdue_multiple_days(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 1),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.label == "Vencida · hace 4 días"

    def test_label_today(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 5),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.label == "Hoy"

    def test_label_tomorrow(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 6),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.label == "Mañana"

    def test_label_future_days(self):
        a = Activity(
            id=1, summary="Test", date_deadline=date(2026, 7, 12),
            activity_type_name="Call", res_model=None, res_id=None,
            partner_name=None, ref_date=date(2026, 7, 5),
        )
        assert a.label == "En 7 días"


class TestOpportunity:
    def test_days_until_deadline(self):
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 20), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.days_until_deadline == 15

    def test_days_until_deadline_none(self):
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=None, partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.days_until_deadline is None

    def test_urgency_red(self):
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 8), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "red"

    def test_urgency_amber(self):
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 12), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "amber"

    def test_urgency_green(self):
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 20), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "green"

    def test_urgency_gray_no_deadline(self):
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=None, partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "gray"

    def test_urgency_red_boundary_3(self):
        """3 días o menos → rojo."""
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 8), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "red"

    def test_urgency_amber_boundary_4(self):
        """4-7 días → ámbar."""
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 9), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "amber"

    def test_urgency_green_boundary_8(self):
        """8+ días → verde."""
        o = Opportunity(
            id=1, name="Test", expected_revenue=100_000, probability=50,
            date_deadline=date(2026, 7, 13), partner_name="Cliente",
            stage_id=None, stage_name="Negociación", ref_date=date(2026, 7, 5),
        )
        assert o.urgency == "green"
