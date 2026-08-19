from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Credenciales de Odoo: configuradas desde variables de entorno o .env,
    odoo_url: str
    odoo_db: str
    odoo_user: str
    odoo_password: str
    odoo_api_key: str | None = None
    odoo_timeout: int = 30
    tz: str = "America/Bogota"
    # En serverless (Cloud Run + Cloud Scheduler) debe ser false: el disparo
    # llega por HTTP y el cron interno duplicaría el envío si la instancia
    # está caliente a la hora programada.
    enable_scheduler: bool = True
    cron_hour: int = 8
    cron_minute: int = 0
    activity_horizon_days: int = 15
    reminder_sender: str = "CRM Comercial <crm@energizar.cloud>"
    db_url: str = "sqlite+aiosqlite:///data/reminder_logs.db"
    skip_holidays: bool = True
    saturday_is_working: bool = False
    # Envío por SMTP (servidor de correo del cliente). El remitente (From)
    # es reminder_sender; smtp_user es la cuenta que autentica en el servidor.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_ssl: bool = False        # True = SSL implícito (puerto 465)
    smtp_starttls: bool = True    # True = STARTTLS (puerto 587, lo usual)

    # extra="ignore": una variable sobrante en el entorno o el .env (p. ej. de
    # una versión anterior) no debe impedir el arranque del servicio.
    model_config = {
        "env_prefix": "", "case_sensitive": False, "env_file": ".env",
        "extra": "ignore",
    }

    @field_validator(
        "odoo_api_key", "smtp_host", "smtp_user", "smtp_password",
        mode="before",
    )
    @classmethod
    def _empty_env_to_none(cls, v):
        return None if v == "" else v

    @field_validator("skip_holidays", "enable_scheduler", "smtp_starttls", mode="before")
    @classmethod
    def _empty_bool_true(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return True
        return v

    @field_validator("saturday_is_working", "smtp_ssl", mode="before")
    @classmethod
    def _empty_bool_false(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return False
        return v


settings = Settings()
