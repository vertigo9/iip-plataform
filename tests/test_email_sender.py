"""Testes unitários com mock para o serviço de envio de e-mails."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from iip.notifications.email_sender import send_html_report_email


@patch("smtplib.SMTP")
def test_send_html_report_email_success(mock_smtp):
    instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = instance

    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = Path(tmpdir) / "test_report.html"
        report_file.write_text("<h1>Relatorio Teste</h1>", encoding="utf-8")

        config = {
            "host": "smtp.test.com",
            "port": 25,
            "sender_email": "test@iip.com",
        }

        success = send_html_report_email(
            report_html_path=report_file,
            smtp_config=config,
            recipient_email="investidor@exemplo.com",
        )

        assert success is True
        assert instance.send_message.called
