from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class OdooUser:
    id: int
    name: str
    email: str | None
    tz: str | None


@dataclass
class Activity:
    id: int
    summary: str | None
    date_deadline: date
    activity_type_name: str | None
    res_model: str | None
    res_id: int | None
    partner_name: str | None
    ref_date: date

    @property
    def urgency(self) -> str:
        if self.date_deadline < self.ref_date:
            return "overdue"
        if self.date_deadline == self.ref_date:
            return "today"
        return "upcoming"

    @property
    def label(self) -> str:
        overdue_days = (self.ref_date - self.date_deadline).days
        if overdue_days == 1:
            return "Vencida · ayer"
        if overdue_days > 1:
            return f"Vencida · hace {overdue_days} días"
        if overdue_days == 0:
            return "Hoy"
        if overdue_days == -1:
            return "Mañana"
        return f"En {-overdue_days} días"


@dataclass
class Opportunity:
    id: int
    name: str
    expected_revenue: float
    probability: float
    date_deadline: date | None
    partner_name: str | None
    stage_id: int | None
    stage_name: str | None
    ref_date: date

    @property
    def days_until_deadline(self) -> int | None:
        if self.date_deadline:
            return (self.date_deadline - self.ref_date).days
        return None

    @property
    def urgency(self) -> str:
        if self.days_until_deadline is None:
            return "gray"
        if self.days_until_deadline <= 3:
            return "red"
        if self.days_until_deadline <= 7:
            return "amber"
        return "green"
