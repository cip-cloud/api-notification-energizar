"""Fixtures compartidos para todos los tests."""

from collections.abc import AsyncGenerator
from datetime import date
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.models.log import Base, ReminderLog

# ---------------------------------------------------------------------------
# Override de Settings para tests
# ---------------------------------------------------------------------------

TEST_ODOO_URL = "http://test.odoo.local"
TEST_ODOO_DB = "test_db"
TEST_ODOO_USER = "test_user"
TEST_ODOO_PASSWORD = "test_pass"
TEST_DB_URL = "sqlite+aiosqlite://"  # in-memory

@pytest.fixture(autouse=True)
def override_settings():
    """Sobreescribe globalmente app.config.settings con valores de test.

    Se ejecuta automáticamente en cada test.  Parchea el módulo en caliente
    para que cualquier import posterior vea el settings de prueba.
    """
    with patch("app.config.settings") as mock:
        mock.odoo_url = TEST_ODOO_URL
        mock.odoo_db = TEST_ODOO_DB
        mock.odoo_user = TEST_ODOO_USER
        mock.odoo_password = TEST_ODOO_PASSWORD
        mock.odoo_api_key = None
        mock.odoo_timeout = 5
        mock.tz = "America/Bogota"
        mock.cron_hour = 8
        mock.cron_minute = 0
        mock.reminder_sender = "Test <test@test.local>"
        mock.db_url = TEST_DB_URL
        yield


# ---------------------------------------------------------------------------
# Mock del OdooClient singleton
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_odoo_client():
    """Reemplaza OdooClient() con un MagicMock para evitar llamadas reales.

    Parchea tanto ``app.odoo.client.OdooClient`` como
    ``app.odoo.queries.OdooClient`` porque queries.py importa la clase
    directamente a nivel de módulo (``from app.odoo.client import OdooClient``),
    lo que crea una referencia local que la primera patch no alcanza.

    Las pruebas unitarias de queries.py pueden personalizar el retorno
    accediendo a ``OdooClient().search_read`` etc.
    """
    mock_client_class = MagicMock()
    with patch("app.odoo.client.OdooClient", mock_client_class), \
         patch("app.odoo.queries.OdooClient", mock_client_class):
        instance = MagicMock()
        mock_client_class.return_value = instance
        # Atajos comunes para que el código no explote al acceder
        instance.search_read.return_value = []
        instance.search.return_value = []
        instance.read.return_value = []
        # uid cached_property mockea automáticamente; no necesita red
        yield instance


# ---------------------------------------------------------------------------
# Base de datos en memoria (aislada por test)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    """Crea un engine SQLite asíncrono en memoria y corre las migraciones."""
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Session de base de datos (commit explícito para ver los datos)."""
    async with AsyncSession(db_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI test client (App + dependencias sobreescritas)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_app(db_engine) -> FastAPI:
    """App FastAPI temporal con engine de test inyectado.

    Parchea el engine global de app.models.log para que los routers usen la BD
    de test en lugar de la de producción.
    """
    with patch("app.models.log.engine", db_engine):
        with patch("app.dependencies.engine", db_engine):
            from app.main import app
            yield app


@pytest_asyncio.fixture
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient de HTTPX para golpear los endpoints de la app de test."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Datos de ejemplo compartidos
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_activities() -> list[dict]:
    return [
        {
            "id": 1, "summary": "Llamada de seguimiento",
            "date_deadline": date(2026, 6, 29),
            "user_id": [6, "Alejandro Viveros"],
            "activity_type_id": [2, "Call"],
            "res_model": "crm.lead", "res_id": 100,
        },
        {
            "id": 2, "summary": "Enviar cotización",
            "date_deadline": date(2026, 7, 8),
            "user_id": [6, "Alejandro Viveros"],
            "activity_type_id": [5, "Upload Document"],
            "res_model": "crm.lead", "res_id": 101,
        },
    ]


@pytest.fixture
def sample_opportunities() -> list[dict]:
    return [
        {
            "id": 201, "name": "Suministro anual de empaques",
            "expected_revenue": 48_000_000.0, "probability": 75.0,
            "date_deadline": date(2026, 7, 15),
            "partner_id": [50, "Comercializadora Andina"],
            "stage_id": [4, "Negociación"],
            "user_id": [6, "Alejandro Viveros"],
        },
        {
            "id": 202, "name": "Renovación contrato logística",
            "expected_revenue": 25_000_000.0, "probability": 50.0,
            "date_deadline": date(2026, 7, 22),
            "partner_id": [51, "Distribuidora del Valle"],
            "stage_id": [2, "Propuesta"],
            "user_id": [6, "Alejandro Viveros"],
        },
    ]


@pytest.fixture
def sample_users() -> list[dict]:
    return [
        {"id": 6, "name": "Alejandro Viveros", "email": "comercial@energizar.com.co", "tz": "America/Bogota"},
        {"id": 29, "name": "Marlon Baez", "email": "ac01.energizar@energizar.com.co", "tz": "America/Bogota"},
    ]
