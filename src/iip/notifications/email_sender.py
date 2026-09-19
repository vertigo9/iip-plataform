"""Módulo de envio de notificações e relatórios consolidados por e-mail via SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def send_html_report_email(
    report_html_path: Path | str,
    smtp_config: dict[str, Any],
    recipient_email: str,
) -> bool:
    """Envia o relatório HTML consolidado em anexo/corpo de e-mail usando SMTP."""
    report_path = Path(report_html_path)
    if not report_path.exists():
        logger.error("Arquivo de relatório não encontrado: %s", report_path)
        return False

    html_content = report_path.read_text(encoding="utf-8")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "📊 IIP Engine — Relatório Consolidado Diário"
    msg["From"] = smtp_config.get("sender_email", "noreply@iipengine.com")
    msg["To"] = recipient_email

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    host = smtp_config.get("host", "localhost")
    port = int(smtp_config.get("port", 25))
    username = smtp_config.get("username")
    password = smtp_config.get("password")

    try:
        if port == 587:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
        elif port == 465:
            with smtplib.SMTP_SSL(host, port) as server:
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as server:
                if username and password:
                    server.login(username, password)
                server.send_message(msg)

        logger.info(
            "E-mail com relatório enviado com sucesso para: %s", recipient_email
        )
        return True
    # isolamento de falha de envio, não deve derrubar o chamador
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao enviar e-mail via SMTP: %s", exc)
        return False
