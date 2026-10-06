from unittest.mock import MagicMock, patch

from app.integrations.email import SMTPMailer


def test_smtp_starttls_before_authentication(settings):
    settings.smtp_security = "starttls"
    settings.smtp_username = "sender"
    settings.smtp_password = "smtp-password"
    smtp = MagicMock()
    with patch("app.integrations.email.smtplib.SMTP", return_value=smtp):
        SMTPMailer(settings).send_verification("produtor@example.com", "000007", 60)
    connection = smtp.__enter__.return_value
    names = [call[0] for call in connection.method_calls]
    assert names == ["starttls", "login", "send_message"]
    message = connection.send_message.call_args.args[0]
    assert message["To"] == "produtor@example.com"
    assert "000007" in message.get_content()
    assert "60 segundos" in message.get_content()


def test_smtp_ssl_reset_message(settings):
    settings.smtp_security = "ssl"
    smtp = MagicMock()
    with patch("app.integrations.email.smtplib.SMTP_SSL", return_value=smtp) as constructor:
        SMTPMailer(settings).send_password_reset("produtor@example.com", "reset-token")
    assert constructor.call_args.kwargs["context"]
    message = smtp.__enter__.return_value.send_message.call_args.args[0]
    assert "reset-token" in message.get_content()
    assert "15 minutos" in message.get_content()
