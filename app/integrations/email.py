import smtplib
import ssl
from email.message import EmailMessage


class SMTPMailer:
    def __init__(self, settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str):
        settings = self.settings
        message = EmailMessage()
        message["From"] = settings.mail_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        cls = smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP
        kwargs = {"timeout": settings.smtp_timeout}
        if settings.smtp_security == "ssl":
            kwargs["context"] = ssl.create_default_context()
        with cls(settings.smtp_host, settings.smtp_port, **kwargs) as smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

    def send_verification(self, to: str, code: str, expires_seconds: int):
        self.send(
            to,
            "Confirme sua conta AgroLab",
            f"Seu código AgroLab é {code}.\nVálido por {expires_seconds} segundos a partir da emissão.\n"
            "Se você não solicitou este cadastro, ignore esta mensagem.",
        )

    def send_password_reset(self, to: str, token: str):
        self.send(
            to,
            "Recuperação de senha AgroLab",
            f"Use este token na tela de recuperação do aplicativo:\n{token}\n"
            "Válido por 15 minutos. Se você não solicitou, ignore esta mensagem.",
        )
