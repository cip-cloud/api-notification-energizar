from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_holidays_by_year: dict[int, set[date]] = {}
HOLIDAYS_API = "https://date.nager.at/api/v3/PublicHolidays/{year}/CO"


async def _fetch_holidays(year: int) -> set[date]:
    url = HOLIDAYS_API.format(year=year)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            dates = set()
            for h in resp.json():
                try:
                    dates.add(date.fromisoformat(h["date"]))
                except (ValueError, KeyError):
                    continue
            logger.info("Fetched %d Colombian holidays for %d", len(dates), year)
            return dates
    except Exception as e:
        logger.warning("Failed to fetch holidays from %s: %s", url, e)
        return set()


async def get_holidays(year: int) -> set[date]:
    if year not in _holidays_by_year:
        _holidays_by_year[year] = await _fetch_holidays(year)
    return _holidays_by_year[year]


async def is_holiday_today() -> bool:
    today = datetime.now(ZoneInfo(settings.tz)).date()
    holidays = await get_holidays(today.year)
    return today in holidays
