from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    jwt_secret: str = Field(min_length=32)
    otp_secret: str = Field(min_length=32)
    jwt_issuer: str = "agrolab-development"
    jwt_audience: str = "agrolab-ios-development"
    bcrypt_cost: int = Field(default=12, ge=10, le=16)
    access_seconds: int = Field(default=900, ge=60, le=900)
    session_seconds: int = Field(default=604800, ge=900, le=604800)
    privacy_policy_version: str = "2026-10-06"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_security: Literal["none", "starttls", "ssl"] = "none"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_timeout: int = Field(default=10, ge=1, le=30)
    mail_from: str = "AgroLab <noreply@agrolab.local>"
    db_pool_size: int = Field(default=5, ge=1, le=50)

    @model_validator(mode="after")
    def secure_configuration(self):
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL deve usar PostgreSQL com psycopg")
        if self.jwt_secret == self.otp_secret:
            raise ValueError("JWT_SECRET e OTP_SECRET precisam ser distintos")
        if self.environment == "production":
            for secret in (self.jwt_secret, self.otp_secret):
                if len(secret) < 64 or any(
                    x in secret.lower() for x in ("change_me", "test", "example")
                ):
                    raise ValueError(
                        "Segredos de produção devem ser aleatórios e ter pelo menos 64 caracteres"
                    )
            if "development" in self.jwt_issuer or "development" in self.jwt_audience:
                raise ValueError("Produção requer JWT_ISSUER e JWT_AUDIENCE próprios")
            if self.smtp_security == "none" or not self.smtp_username or not self.smtp_password:
                raise ValueError("Produção requer SMTP autenticado com TLS")
            if "agrolab.local" in self.mail_from:
                raise ValueError("Produção requer remetente de e-mail verificado")
        return self
