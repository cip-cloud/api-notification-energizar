from __future__ import annotations

from pydantic import BaseModel


class ReminderResult(BaseModel):
    user_id: int
    user_email: str
    activities_count: int
    opportunities_count: int
    status: str


class ReminderResponse(BaseModel):
    total: int
    sent: int
    failed: int
    results: list[ReminderResult]


class TestReminderRequest(BaseModel):
    to_email: str = "correo-de-prueba@ejemplo.com"
    user_email: str | None = None
