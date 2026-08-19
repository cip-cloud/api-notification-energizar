from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class LogEntry(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_name: str | None
    activities_count: int
    opportunities_count: int
    status: str
    error_message: str | None
    sent_at: datetime

    model_config = {"from_attributes": True}


class LogStats(BaseModel):
    total_sent: int
    total_failed: int
    total_errors: int
    today_sent: int
    unique_users: int
