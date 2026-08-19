from __future__ import annotations

from datetime import date, datetime, timedelta

from app.config import settings
from app.odoo.client import OdooClient
from app.odoo.models import OdooUser, Activity, Opportunity


def _parse_date(value) -> date | None:
    # Odoo serializa campos Date como string "YYYY-MM-DD" vía XML-RPC
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _m2o(value) -> tuple[int | None, str | None]:
    # Odoo devuelve many2one como [id, display_name], o False si está vacío
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    if isinstance(value, int) and not isinstance(value, bool):
        return value, None
    return None, None


def _get_catalog_names(client: OdooClient, model: str) -> dict[int, str]:
    records = client.search_read(model, [], ["id", "name"])
    return {r["id"]: r["name"] for r in records}


def get_sales_users() -> list[OdooUser]:
    client = OdooClient()
    users = client.search_read(
        "res.users",
        [["share", "=", False]],
        ["id", "name", "email", "tz"],
    )
    return [
        OdooUser(
            id=u["id"],
            name=u["name"],
            email=u.get("email") or None,
            tz=u.get("tz") or None,
        )
        for u in users
    ]


def get_pending_activities(
    user_ids: list[int], ref_date: date, horizon_days: int | None = None
) -> dict[int, list[Activity]]:
    """Actividades pendientes de todos los usuarios en una sola consulta,
    agrupadas por user_id. Incluye hasta `horizon_days` hacia adelante
    (por defecto ACTIVITY_HORIZON_DAYS) para mostrar también las próximas."""
    if horizon_days is None:
        horizon_days = settings.activity_horizon_days
    client = OdooClient()
    horizon = ref_date + timedelta(days=horizon_days)
    raw = client.search_read(
        "mail.activity",
        [
            ["user_id", "in", user_ids],
            ["date_deadline", "<=", horizon.isoformat()],
        ],
        ["id", "summary", "date_deadline", "user_id", "activity_type_id", "res_model", "res_id"],
        order="date_deadline ASC",
    )
    type_names = _get_catalog_names(client, "mail.activity.type")
    partner_names = _resolve_partner_names(client, raw)

    result: dict[int, list[Activity]] = {}
    for a in raw:
        user_id, _ = _m2o(a.get("user_id"))
        type_id, type_label = _m2o(a.get("activity_type_id"))
        res_model = a.get("res_model") or None
        res_id = a.get("res_id") or None
        result.setdefault(user_id, []).append(Activity(
            id=a["id"],
            summary=a.get("summary") or None,
            date_deadline=_parse_date(a.get("date_deadline")),
            activity_type_name=type_names.get(type_id) or type_label,
            res_model=res_model,
            res_id=res_id,
            partner_name=partner_names.get((res_model, res_id)),
            ref_date=ref_date,
        ))
    return result


def _resolve_partner_names(client: OdooClient, raw_activities: list[dict]) -> dict[tuple[str, int], str | None]:
    ids_by_model: dict[str, set[int]] = {}
    for a in raw_activities:
        model, res_id = a.get("res_model"), a.get("res_id")
        if model in ("crm.lead", "res.partner") and res_id:
            ids_by_model.setdefault(model, set()).add(res_id)

    names: dict[tuple[str, int], str | None] = {}
    lead_ids = ids_by_model.get("crm.lead")
    if lead_ids:
        for lead in client.search_read("crm.lead", [["id", "in", list(lead_ids)]], ["id", "partner_id"]):
            _, partner_name = _m2o(lead.get("partner_id"))
            names[("crm.lead", lead["id"])] = partner_name
    partner_ids = ids_by_model.get("res.partner")
    if partner_ids:
        for partner in client.search_read("res.partner", [["id", "in", list(partner_ids)]], ["id", "name"]):
            names[("res.partner", partner["id"])] = partner.get("name") or None
    return names


def get_opportunities(
    user_ids: list[int], ref_date: date, horizon_days: int = 15
) -> dict[int, list[Opportunity]]:
    """Oportunidades próximas a cierre de todos los usuarios en una sola
    consulta, agrupadas por user_id."""
    client = OdooClient()
    deadline_end = ref_date + timedelta(days=horizon_days)
    domain: list = [
        ["user_id", "in", user_ids],
        ["type", "=", "opportunity"],
        ["active", "=", True],
        ["probability", "<", 100],
        ["stage_id.is_won", "=", False],
        "|",
        ["date_deadline", "=", False],
        "&",
        ["date_deadline", ">=", ref_date.isoformat()],
        ["date_deadline", "<=", deadline_end.isoformat()],
    ]
    raw = client.search_read(
        "crm.lead",
        domain,
        ["id", "name", "expected_revenue", "probability", "date_deadline", "partner_id", "stage_id", "user_id"],
        order="date_deadline ASC",
    )
    return {uid: _build_opportunities(client, uid, raw) for uid in set(
        _m2o(r.get("user_id"))[0] for r in raw
    )}


def get_opportunities_by_ids(lead_ids: list[int]) -> list[Opportunity]:
    """Oportunidades/leads específicas (sin filtro de tipo ni fecha). Se usa
    para traer las oportunidades a las que apuntan las actividades, aunque no
    estén próximas a cierre."""
    if not lead_ids:
        return []
    client = OdooClient()
    domain: list = [
        ["id", "in", list(set(lead_ids))],
        ["active", "=", True],
        ["stage_id.is_won", "=", False],
    ]
    raw = client.search_read(
        "crm.lead",
        domain,
        ["id", "name", "expected_revenue", "probability", "date_deadline", "partner_id", "stage_id", "user_id"],
    )
    return _build_opportunities(client, None, raw)


def _build_opportunities(client: OdooClient, user_id: int | None, raw: list[dict]) -> list[Opportunity]:
    stage_names = _get_catalog_names(client, "crm.stage")
    result: list[Opportunity] = []
    for lead in raw:
        uid, _ = _m2o(lead.get("user_id"))
        if user_id is not None and uid != user_id:
            continue
        _, partner_name = _m2o(lead.get("partner_id"))
        stage_id, stage_label = _m2o(lead.get("stage_id"))
        result.append(Opportunity(
            id=lead["id"],
            name=lead.get("name") or "",
            expected_revenue=float(lead.get("expected_revenue") or 0),
            probability=float(lead.get("probability") or 0),
            date_deadline=_parse_date(lead.get("date_deadline")),
            partner_name=partner_name,
            stage_id=stage_id,
            stage_name=stage_names.get(stage_id) or stage_label,
            ref_date=date.today(),
        ))
    return result

