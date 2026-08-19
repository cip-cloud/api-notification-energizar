from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

from app.config import settings
from app.emails.smtp import send_email_via_smtp

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))

_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
           "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _format_date(d: date) -> str:
    return f"{_WEEKDAYS[d.weekday()]} {d.day} de {_MONTHS[d.month - 1]}"


def render_reminder(user_name: str, date_str: str, activities: list[dict], opportunities: list[dict]) -> str:
    template = _env.get_template("reminder.html")
    opp_ids = {o["id"] for o in opportunities if o.get("id")}
    orphan_activities = [
        a for a in activities if a.get("opp_id") not in opp_ids or not a.get("opp_id")
    ]
    return template.render(
        user_name=user_name,
        date=date_str,
        activities=orphan_activities,
        total_activities=len(activities),
        opportunities=opportunities,
        odoo_url=settings.odoo_url,
    )


async def send_email(to_email: str, subject: str, html_body: str) -> bool:
    return await send_email_via_smtp(to_email, subject, html_body)


async def send_reminder(to_email: str, user_name: str, activities: list[dict], opportunities: list[dict],
                        ref_date: date | None = None) -> bool:
    today = ref_date or datetime.now(ZoneInfo(settings.tz)).date()
    date_str = _format_date(today)

    html = render_reminder(user_name, date_str, activities, opportunities)
    subject = f"🔔 Energizar SAS — Tu resumen comercial — {date_str}"

    return await send_email(to_email, subject, html)
