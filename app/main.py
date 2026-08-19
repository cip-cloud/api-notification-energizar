from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.cron.daily import scheduler, setup_scheduler
from app.models.log import engine, Base
from app.routers import reminders, logs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if settings.enable_scheduler:
        setup_scheduler()
        scheduler.start()
    yield
    if settings.enable_scheduler:
        scheduler.shutdown()


app = FastAPI(
    title="Energizar — Recordatorios Comerciales",
    description="API de recordatorios automáticos desde Odoo 15 Enterprise",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "tz": settings.tz}


app.include_router(reminders.router)
app.include_router(logs.router)
