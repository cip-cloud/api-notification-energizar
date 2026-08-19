from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_session
from app.models.log import ReminderLog
from app.schemas.log import LogEntry, LogStats

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("", response_model=list[LogEntry])
async def list_logs(limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ReminderLog).order_by(ReminderLog.sent_at.desc()).offset(offset).limit(limit)
    )
    return [LogEntry.model_validate(l) for l in result.scalars().all()]


@router.get("/stats", response_model=LogStats)
async def log_stats(session: AsyncSession = Depends(get_session)):
    by_status = await session.execute(
        select(ReminderLog.status, func.count()).group_by(ReminderLog.status)
    )
    counts = dict(by_status.all())

    # sent_at se guarda en UTC naive; "hoy" se define en la TZ del negocio
    tz = ZoneInfo(settings.tz)
    local_midnight = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz)
    today_start = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)

    today_q = await session.execute(
        select(func.count())
        .select_from(ReminderLog)
        .where(ReminderLog.sent_at >= today_start, ReminderLog.status == "sent")
    )
    users_q = await session.execute(
        select(func.count(func.distinct(ReminderLog.user_id)))
    )

    return LogStats(
        total_sent=counts.get("sent", 0),
        total_failed=counts.get("failed", 0),
        total_errors=counts.get("error", 0),
        today_sent=today_q.scalar() or 0,
        unique_users=users_q.scalar() or 0,
    )
