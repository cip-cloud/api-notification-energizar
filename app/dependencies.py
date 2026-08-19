from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import engine


async def get_session():
    async with AsyncSession(engine) as session:
        yield session
