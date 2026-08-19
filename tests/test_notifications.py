"""Tests para la lógica de no-repetición de notificaciones (app/notifications.py)."""

from datetime import date

import pytest
import pytest_asyncio

from app.models.log import NotifiedActivity, NotifiedOpportunity
from app.notifications import (
    load_notified_state,
    record_activities,
    record_opportunities,
    select_opportunities_to_notify,
)
from app.odoo.models import Activity, Opportunity


def _opp(oid: int, stage_id: int | None) -> Opportunity:
    return Opportunity(
        id=oid, name=f"Opp {oid}", expected_revenue=1000, probability=50,
        date_deadline=date(2026, 8, 1), partner_name="Client",
        stage_id=stage_id, stage_name=str(stage_id), ref_date=date(2026, 7, 31),
    )


def _act(aid: int, opp_id: int | None) -> Activity:
    return Activity(
        id=aid, summary=f"Act {aid}", date_deadline=date(2026, 7, 31),
        activity_type_name="Call", res_model="crm.lead" if opp_id else None,
        res_id=opp_id, partner_name=None, ref_date=date(2026, 7, 31),
    )


class TestSelectOpportunitiesToNotify:
    def test_new_opportunity_is_selected(self):
        result = select_opportunities_to_notify(
            [_opp(1, 3)], {}, {}, set(),
        )
        assert [o.id for o in result] == [1]

    def test_same_stage_no_activity_not_selected(self):
        result = select_opportunities_to_notify(
            [_opp(1, 3)], {}, {1: 3}, set(),
        )
        assert result == []

    def test_stage_change_is_selected(self):
        result = select_opportunities_to_notify(
            [_opp(1, 4)], {}, {1: 3}, set(),
        )
        assert [o.id for o in result] == [1]

    def test_new_activity_re_notifies(self):
        acts = {1: [_act(100, 1)]}
        result = select_opportunities_to_notify(
            [_opp(1, 3)], acts, {1: 3}, set(),
        )
        assert [o.id for o in result] == [1]

    def test_known_activity_does_not_re_notify(self):
        acts = {1: [_act(100, 1)]}
        result = select_opportunities_to_notify(
            [_opp(1, 3)], acts, {1: 3}, {100},
        )
        assert result == []

    def test_mixed(self):
        """Solo se seleccionan: nueva (1), cambiada (2), con act nueva (3)."""
        acts = {3: [_act(300, 3)]}
        result = select_opportunities_to_notify(
            [_opp(1, 3), _opp(2, 4), _opp(3, 5), _opp(4, 6)],
            acts,
            {2: 3, 3: 5, 4: 6},   # 1 no está → nueva; 2 cambió; 3 igual+act nueva; 4 igual sin act
            {350},
        )
        assert [o.id for o in result] == [1, 2, 3]


class TestNotificationsDb:
    @pytest_asyncio.fixture
    async def known_state(self, db_session):
        db_session.add(NotifiedOpportunity(user_id=6, opportunity_id=10, stage_id=3))
        db_session.add(NotifiedActivity(user_id=6, activity_id=500))
        await db_session.commit()
        return db_session

    async def test_load_notified_state(self, known_state):
        stages, acts = await load_notified_state(known_state, 6)
        assert stages == {10: 3}
        assert acts == {500}

    async def test_load_notified_state_empty(self, db_session):
        stages, acts = await load_notified_state(db_session, 99)
        assert stages == {}
        assert acts == set()

    async def test_record_opportunities_upserts(self, db_session):
        await record_opportunities(db_session, 6, [_opp(10, 4), _opp(11, 1)])
        await db_session.commit()

        stages, _ = await load_notified_state(db_session, 6)
        # 10 se actualizó a etapa 4, 11 es nuevo
        assert stages == {10: 4, 11: 1}

    async def test_record_activities_idempotent(self, db_session):
        await record_activities(db_session, 6, {100, 200})
        await record_activities(db_session, 6, {200, 300})
        await db_session.commit()

        _, acts = await load_notified_state(db_session, 6)
        assert acts == {100, 200, 300}
