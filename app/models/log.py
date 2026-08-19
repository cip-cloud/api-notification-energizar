from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings


engine = create_async_engine(settings.db_url, echo=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), nullable=True)
    activities_count: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NotifiedOpportunity(Base):
    """Oportunidades ya notificadas por usuario, con la etapa que se les vio por
    última vez. Sirve para no repetir una oportunidad en el correo salvo que
    cambie de etapa o reciba una actividad nueva."""

    __tablename__ = "notified_opportunities"
    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_notified_opp_user_opp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    opportunity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_notified_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NotifiedActivity(Base):
    """Actividades ya notificadas por usuario. Permite detectar qué actividades
    son nuevas (no registradas) para re-notificar su oportunidad."""

    __tablename__ = "notified_activities"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_id", name="uq_notified_act_user_act"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_notified_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
