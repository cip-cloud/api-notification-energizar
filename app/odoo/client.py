from __future__ import annotations

import xmlrpc.client
from functools import cached_property

from app.config import settings


class OdooError(RuntimeError):
    """Error de comunicación o de servidor al consultar Odoo."""


def _make_transport(timeout: int) -> xmlrpc.client.Transport:
    base = (
        xmlrpc.client.SafeTransport
        if settings.odoo_url.startswith("https")
        else xmlrpc.client.Transport
    )

    class TimeoutTransport(base):
        def make_connection(self, host):
            conn = super().make_connection(host)
            conn.timeout = timeout
            return conn

    return TimeoutTransport(use_datetime=True)


class OdooClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def _credential(self) -> str:
        return settings.odoo_api_key or settings.odoo_password

    def _proxy(self, endpoint: str) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(
            f"{settings.odoo_url}/xmlrpc/2/{endpoint}",
            transport=_make_transport(settings.odoo_timeout),
        )

    @cached_property
    def common(self):
        return self._proxy("common")

    @cached_property
    def models(self):
        return self._proxy("object")

    @cached_property
    def uid(self):
        try:
            uid = self.common.authenticate(
                settings.odoo_db,
                settings.odoo_user,
                self._credential,
                {},
            )
        except xmlrpc.client.Fault as e:
            raise OdooError(f"Fallo al autenticar con Odoo: {e.faultString}") from e
        except OSError as e:
            raise OdooError(f"No se pudo conectar a Odoo ({settings.odoo_url}): {e}") from e
        if not uid:
            raise OdooError("Autenticación con Odoo fallida: credenciales inválidas")
        return uid

    def execute(self, model: str, method: str, *args, **kwargs):
        try:
            return self.models.execute_kw(
                settings.odoo_db,
                self.uid,
                self._credential,
                model,
                method,
                *args,
                **kwargs,
            )
        except xmlrpc.client.Fault as e:
            raise OdooError(f"Odoo respondió con error en {model}.{method}: {e.faultString}") from e
        except OSError as e:
            raise OdooError(f"No se pudo conectar a Odoo ({settings.odoo_url}): {e}") from e

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        if limit:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order
        return self.execute(model, "search_read", [domain], kwargs)

    def search(self, model: str, domain: list, limit: int | None = None) -> list[int]:
        kwargs = {}
        if limit:
            kwargs["limit"] = limit
        return self.execute(model, "search", [domain], kwargs)

    def read(self, model: str, ids: list[int], fields: list[str] | None = None) -> list[dict]:
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        return self.execute(model, "read", [ids], kwargs)
