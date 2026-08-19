from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import NotifiedActivity, NotifiedOpportunity
from app.odoo.models import Activity, Opportunity


def select_opportunities_to_notify(
    opportunities: list[Opportunity],
    acts_by_opp_id: dict[int, list[Activity]],
    known_stages: dict[int, int | None],
    known_activity_ids: set[int],
) -> list[Opportunity]:
    """Filtra las oportunidades que deben mostrarse en el correo de hoy.

    Una oportunidad se notifica si:
    - es nueva (no existe registro previo), o
    - cambió de etapa (stage_id distinto al registrado), o
    - tiene al menos una actividad nueva (no notificada antes).
    """
    result: list[Opportunity] = []
    for opp in opportunities:
        if opp.id not in known_stages:
            result.append(opp)
            continue
        if known_stages.get(opp.id) != opp.stage_id:
            result.append(opp)
            continue
        opp_acts = acts_by_opp_id.get(opp.id, [])
        if any(a.id not in known_activity_ids for a in opp_acts):
            result.append(opp)
    return result


async def load_notified_state(
    session: AsyncSession, user_id: int
) -> tuple[dict[int, int | None], set[int]]:
    """Carga el estado previo de notificaciones del usuario.

    Devuelve (etapas conocidas por oportunidad, IDs de actividades conocidas).
    """
    opp_rows = await session.execute(
        select(NotifiedOpportunity.opportunity_id, NotifiedOpportunity.stage_id)
        .where(NotifiedOpportunity.user_id == user_id)
    )
    known_stages = {oid: stage for oid, stage in opp_rows.all()}

    act_rows = await session.execute(
        select(NotifiedActivity.activity_id)
        .where(NotifiedActivity.user_id == user_id)
    )
    known_activity_ids = set(act_rows.scalars())
    return known_stages, known_activity_ids


async def record_opportunities(
    session: AsyncSession, user_id: int, opportunities: list[Opportunity]
) -> None:
    """Registra (upsert) las oportunidades notificadas con su etapa actual."""
    for opp in opportunities:
        existing = await session.scalar(
            select(NotifiedOpportunity)
            .where(
                NotifiedOpportunity.user_id == user_id,
                NotifiedOpportunity.opportunity_id == opp.id,
            )
        )
        if existing is None:
            session.add(NotifiedOpportunity(
                user_id=user_id,
                opportunity_id=opp.id,
                stage_id=opp.stage_id,
            ))
        elif existing.stage_id != opp.stage_id:
            existing.stage_id = opp.stage_id


async def record_activities(
    session: AsyncSession, user_id: int, activity_ids: set[int]
) -> None:
    """Registra las actividades notificadas (se ignora si ya existen)."""
    existing_ids = set((await session.execute(
        select(NotifiedActivity.activity_id)
        .where(
            NotifiedActivity.user_id == user_id,
            NotifiedActivity.activity_id.in_(list(activity_ids)),
        )
    )).scalars())
    for aid in activity_ids - existing_ids:
        session.add(NotifiedActivity(user_id=user_id, activity_id=aid))
