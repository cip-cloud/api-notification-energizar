"""Tests para las funciones de consulta a Odoo (queries.py).

Todas las consultas reales están mockeadas por el fixture ``mock_odoo_client``
de conftest.py, que reemplaza OdooClient() por un MagicMock.
"""

from datetime import date

from app.odoo.queries import (
    get_pending_activities,
    get_opportunities,
    get_sales_users,
    _parse_date,
    _m2o,
)


# ---------------------------------------------------------------------------
# Funciones auxiliares (_parse_date, _m2o)
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_from_string(self):
        assert _parse_date("2026-07-05") == date(2026, 7, 5)

    def test_from_date_obj(self):
        assert _parse_date(date(2026, 7, 5)) == date(2026, 7, 5)

    def test_from_none(self):
        assert _parse_date(None) is None

    def test_from_empty_string(self):
        assert _parse_date("") is None

    def test_from_false(self):
        assert _parse_date(False) is None


class TestM2O:
    def test_list_pair(self):
        id_, name = _m2o([6, "Alejandro"])
        assert id_ == 6
        assert name == "Alejandro"

    def test_false(self):
        id_, name = _m2o(False)
        assert id_ is None
        assert name is None

    def test_int_only(self):
        id_, name = _m2o(6)
        assert id_ == 6
        assert name is None


# ---------------------------------------------------------------------------
# get_sales_users
# ---------------------------------------------------------------------------

class TestGetSalesUsers:
    def test_returns_list_of_odoo_user(self, mock_odoo_client, sample_users):
        mock_odoo_client.search_read.return_value = sample_users

        users = get_sales_users()

        assert len(users) == 2
        assert users[0].name == "Alejandro Viveros"
        assert users[0].email == "comercial@energizar.com.co"
        assert users[0].tz == "America/Bogota"
        mock_odoo_client.search_read.assert_called_once()

    def test_empty(self, mock_odoo_client):
        mock_odoo_client.search_read.return_value = []
        assert get_sales_users() == []


# ---------------------------------------------------------------------------
# get_pending_activities
# ---------------------------------------------------------------------------

class TestGetPendingActivities:
    def test_returns_dict_keyed_by_user_id(self, mock_odoo_client, sample_activities):
        mock_odoo_client.search_read.side_effect = [
            sample_activities,              # 1er call: mail.activity
            [{"id": 2, "name": "Call"},     # 2do call: mail.activity.type
             {"id": 5, "name": "Upload Document"}],
            [{"id": 100, "partner_id": [50, "Cliente A"]}],  # crm.lead
        ]

        result = get_pending_activities([6], date(2026, 7, 8))

        assert 6 in result
        acts = result[6]
        assert len(acts) == 2
        assert acts[0].summary == "Llamada de seguimiento"
        assert acts[0].activity_type_name == "Call"

    def test_unknown_user_not_in_result(self, mock_odoo_client):
        mock_odoo_client.search_read.return_value = []
        mock_odoo_client.search_read.side_effect = [
            [],                             # mail.activity
            [],                             # mail.activity.type
            [],                             # crm.lead
        ]
        result = get_pending_activities([99], date(2026, 7, 8))
        assert 99 not in result


# ---------------------------------------------------------------------------
# get_opportunities
# ---------------------------------------------------------------------------

class TestGetOpportunities:
    def test_returns_dict_keyed_by_user_id(self, mock_odoo_client, sample_opportunities):
        mock_odoo_client.search_read.side_effect = [
            sample_opportunities,              # 1er call: crm.lead
            [{"id": 4, "name": "Negociación"},
             {"id": 2, "name": "Propuesta"}],  # 2do call: crm.stage names
        ]

        result = get_opportunities([6], date(2026, 7, 8))

        assert 6 in result
        opps = result[6]
        assert len(opps) == 2
        assert opps[0].name == "Suministro anual de empaques"
        assert opps[0].partner_name == "Comercializadora Andina"
        assert opps[0].stage_name == "Negociación"

    def test_domain_excludes_inactive_and_won(self, mock_odoo_client, sample_opportunities):
        """El dominio enviado a Odoo debe excluir oportunidades archivadas
        (perdidas) y las que están en una etapa ganada."""
        mock_odoo_client.search_read.side_effect = [
            [sample_opportunities[1]],            # crm.lead
            [{"id": 2, "name": "Propuesta"}],     # crm.stage names
        ]

        result = get_opportunities([6], date(2026, 7, 8))

        opps = result[6]
        assert len(opps) == 1
        assert opps[0].id == 202
        called = mock_odoo_client.search_read.call_args_list
        lead_call = called[0]
        domain = lead_call.args[1]
        assert ["active", "=", True] in domain
        assert ["stage_id.is_won", "=", False] in domain

    def test_empty_when_no_opportunities(self, mock_odoo_client):
        mock_odoo_client.search_read.return_value = []
        result = get_opportunities([6], date(2026, 7, 8))
        assert result == {}  # sin oportunidades el dict queda vacío
