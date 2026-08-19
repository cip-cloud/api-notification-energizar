from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.holidays import is_holiday_today
from app.odoo.models import Activity
from app.odoo.queries import (
    get_sales_users, get_pending_activities, get_opportunities,
    get_opportunities_by_ids,
)
from app.emails.sender import send_reminder
from app.models.log import ReminderLog, engine
from app.notifications import (
    load_notified_state, record_activities, record_opportunities,
    select_opportunities_to_notify,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _revenue_label(revenue: float) -> str:
    if revenue >= 1_000_000:
        return f"${revenue / 1_000_000:g}M"
    return f"${revenue:,.0f}"


async def run_daily_reminders() -> list[dict]:
    """Ejecuta la corrida de recordatorios y devuelve el resultado por usuario."""
    logger.info("Starting daily reminder run")
    today = datetime.now(ZoneInfo(settings.tz)).date()

    weekday = today.weekday()
    if weekday == 6:
        logger.info("Sunday — skipping")
        return []
    if weekday == 5 and not settings.saturday_is_working:
        logger.info("Saturday is not a working day — skipping")
        return []
    if settings.skip_holidays and await is_holiday_today():
        logger.info("Today is a Colombian holiday — skipping")
        return []

    users = await asyncio.to_thread(get_sales_users)
    users = [u for u in users if u.email]
    user_ids = [u.id for u in users]

    activities_by_user = await asyncio.to_thread(get_pending_activities, user_ids, today)
    opportunities_by_user = await asyncio.to_thread(get_opportunities, user_ids, today)

    results: list[dict] = []
    async with AsyncSession(engine) as session:
        for user in users:
            user_activities = activities_by_user.get(user.id, [])
            user_opportunities = opportunities_by_user.get(user.id, [])

            acts_by_opp_id: dict[int, list[Activity]] = {}
            for act in user_activities:
                if act.res_model == "crm.lead" and act.res_id:
                    acts_by_opp_id.setdefault(act.res_id, []).append(act)

            # Incluir las oportunidades a las que apuntan las actividades aunque
            # no estén "próximas a cierre", para que cada oportunidad muestre sus
            # actividades asociadas y el evento del calendario tenga el nombre.
            existing_opp_ids = {o.id for o in user_opportunities}
            activity_opp_ids = [oid for oid in acts_by_opp_id if oid not in existing_opp_ids]
            if activity_opp_ids:
                extra = await asyncio.to_thread(get_opportunities_by_ids, activity_opp_ids)
                user_opportunities = list(user_opportunities) + extra

            # No repetir oportunidades ya notificadas: solo se vuelven a mostrar
            # si son nuevas, cambiaron de etapa o tienen una actividad nueva.
            known_stages, known_activity_ids = await load_notified_state(session, user.id)
            user_opportunities = select_opportunities_to_notify(
                user_opportunities, acts_by_opp_id, known_stages, known_activity_ids
            )

            act_dicts: list[dict] = []
            opp_dicts: list[dict] = []
            try:
                act_dicts = [
                    {
                        "id": a.id,
                        "name": a.summary or a.activity_type_name or "Actividad",
                        "partner": a.partner_name,
                        "urgency": a.urgency,
                        "label": a.label,
                        "date_deadline": a.date_deadline,
                        "opp_id": a.res_id if a.res_model == "crm.lead" else None,
                    }
                    for a in user_activities
                ]
                opp_dicts = [
                    {
                        "id": o.id,
                        "name": o.name,
                        "partner": o.partner_name or "—",
                        "revenue_label": _revenue_label(o.expected_revenue),
                        "days_until": o.days_until_deadline,
                        "probability": int(o.probability),
                        "stage": o.stage_name or "",
                        "urgency": o.urgency,
                        "activities": [
                            {
                                "name": a.summary or a.activity_type_name or "Actividad",
                                "urgency": a.urgency,
                                "label": a.label,
                            }
                            for a in acts_by_opp_id.get(o.id, [])
                        ],
                    }
                    for o in user_opportunities
                ]

                if not act_dicts and not opp_dicts:
                    logger.info("No data for user %s, skipping", user.email)
                    continue

                success = await send_reminder(
                    to_email=user.email,
                    user_name=user.name,
                    activities=act_dicts,
                    opportunities=opp_dicts,
                    ref_date=today,
                )
                status = "sent" if success else "failed"
                error_message = None if success else "Email send returned False"

                if success:
                    await record_opportunities(session, user.id, user_opportunities)
                    await record_activities(
                        session, user.id, {a["id"] for a in act_dicts if a.get("id")}
                    )

            except Exception as e:
                logger.error("Error for user %s: %s", user.email, e)
                status = "error"
                error_message = str(e)

            session.add(ReminderLog(
                user_id=user.id,
                user_email=user.email,
                user_name=user.name,
                activities_count=len(act_dicts),
                opportunities_count=len(opp_dicts),
                status=status,
                error_message=error_message,
            ))
            results.append({
                "user_id": user.id,
                "user_email": user.email,
                "activities_count": len(act_dicts),
                "opportunities_count": len(opp_dicts),
                "status": status,
            })

        await session.commit()

    logger.info("Daily reminder run completed: %d users processed", len(results))
    return results


def setup_scheduler():
    scheduler.remove_all_jobs()
    scheduler.add_job(
        run_daily_reminders,
        "cron",
        hour=settings.cron_hour,
        minute=settings.cron_minute,
        timezone=settings.tz,
        id="daily_reminders",
        replace_existing=True,
    )
