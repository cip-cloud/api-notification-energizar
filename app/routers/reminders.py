from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.cron.daily import _revenue_label, run_daily_reminders
from app.emails.sender import send_reminder
from app.models.log import engine
from app.notifications import load_notified_state, select_opportunities_to_notify
from app.odoo.models import Activity
from app.odoo.queries import (
    get_sales_users, get_pending_activities, get_opportunities,
    get_opportunities_by_ids,
)
from app.schemas.reminder import ReminderResponse, ReminderResult, TestReminderRequest
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Reminders"])


@router.post("/trigger-reminders", response_model=ReminderResponse)
async def trigger_reminders():
    try:
        run_results = await run_daily_reminders()
    except Exception as e:
        logger.error("Reminder run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    results = [ReminderResult(**r) for r in run_results]
    sent = sum(1 for r in results if r.status == "sent")
    failed = sum(1 for r in results if r.status in ("failed", "error"))

    return ReminderResponse(
        total=len(results),
        sent=sent,
        failed=failed,
        results=results,
    )


@router.post("/test-reminder")
async def test_reminder(body: TestReminderRequest):
    to_email = body.to_email
    user_email = body.user_email
    today = datetime.now(ZoneInfo(settings.tz)).date()

    users = await asyncio.to_thread(get_sales_users)
    users = [u for u in users if u.email]
    if not users:
        return {"error": "No sales users with email found"}

    if user_email:
        target = next((u for u in users if u.email == user_email), None)
        if not target:
            return {"error": f"User '{user_email}' not found among sales users"}
        users = [target]

    user_ids = [u.id for u in users]
    acts_by_user = await asyncio.to_thread(get_pending_activities, user_ids, today)
    opps_by_user = await asyncio.to_thread(get_opportunities, user_ids, today)

    user = users[0]
    for u in users:
        if acts_by_user.get(u.id) or opps_by_user.get(u.id):
            user = u
            break

    user_activities = acts_by_user.get(user.id, [])
    user_opportunities = opps_by_user.get(user.id, [])

    acts_by_opp_id: dict[int, list[Activity]] = {}
    for act in user_activities:
        if act.res_model == "crm.lead" and act.res_id:
            acts_by_opp_id.setdefault(act.res_id, []).append(act)

    # Incluir las oportunidades a las que apuntan las actividades aunque no
    # estén "próximas a cierre", para que cada oportunidad muestre sus
    # actividades asociadas y el evento del calendario tenga el nombre.
    existing_opp_ids = {o.id for o in user_opportunities}
    activity_opp_ids = [oid for oid in acts_by_opp_id if oid not in existing_opp_ids]
    if activity_opp_ids:
        extra = await asyncio.to_thread(get_opportunities_by_ids, activity_opp_ids)
        user_opportunities = list(user_opportunities) + extra

    # Aplicar la misma lógica de no-repetición del cron, sin registrar nada
    # (este endpoint solo simula la corrida para el correo de prueba).
    async with AsyncSession(engine) as session:
        known_stages, known_activity_ids = await load_notified_state(session, user.id)
    user_opportunities = select_opportunities_to_notify(
        user_opportunities, acts_by_opp_id, known_stages, known_activity_ids
    )

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

    success = await send_reminder(
        to_email=to_email,
        user_name=user.name,
        activities=act_dicts,
        opportunities=opp_dicts,
        ref_date=today,
    )

    return {
        "sent_to": to_email,
        "original_user": user.name,
        "original_email": user.email,
        "activities_count": len(act_dicts),
        "opportunities_count": len(opp_dicts),
        "success": success,
    }
