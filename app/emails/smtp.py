from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from app.config import settings

logger = logging.getLogger(__name__)


def _build_message(to_email: str, subject: str, html_body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.reminder_sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(
        "Este correo contiene tu resumen comercial en formato HTML. "
        "Ábrelo en un cliente de correo compatible."
    )
    msg.add_alternative(html_body, subtype="html")
    return msg


def _send_sync(to_email: str, subject: str, html_body: str) -> bool:
    msg = _build_message(to_email, subject, html_body)
    context = ssl.create_default_context()

    if settings.smtp_ssl:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                  timeout=30, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)

    with server:
        if not settings.smtp_ssl and settings.smtp_starttls:
            server.starttls(context=context)
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)

    sender_addr = parseaddr(settings.reminder_sender)[1]
    logger.info("Email sent via SMTP to %s as %s", to_email, sender_addr)
    return True


async def send_email_via_smtp(to_email: str, subject: str, html_body: str) -> bool:
    if not settings.smtp_host:
        logger.warning("SMTP not configured — missing SMTP_HOST, skipping email")
        return False
    try:
        # smtplib es bloqueante: se ejecuta en un hilo, igual que las
        # llamadas XML-RPC a Odoo.
        return await asyncio.to_thread(_send_sync, to_email, subject, html_body)
    except (smtplib.SMTPException, OSError) as e:
        logger.error("Failed to send email via SMTP to %s: %s", to_email, e)
        return False
