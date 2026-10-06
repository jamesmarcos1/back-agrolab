import os
import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base
from app.main import create_app


class FakeClock:
    def __init__(self):
        self.value = datetime.now(UTC).replace(microsecond=0)

    def now(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class FakeMailer:
    def __init__(self):
        self.verifications = []
        self.resets = []
        self.fail = False
        self.lock = threading.Lock()

    def send_verification(self, to, code, expires_seconds):
        if self.fail:
            raise OSError("SMTP unavailable")
        with self.lock:
            self.verifications.append((to, code, expires_seconds))

    def send_password_reset(self, to, token):
        if self.fail:
            raise OSError("SMTP unavailable")
        with self.lock:
            self.resets.append((to, token))


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        environment="test",
        database_url=os.environ["TEST_DATABASE_URL"],
        jwt_secret="test-jwt-" + "a" * 64,
        otp_secret="test-otp-" + "b" * 64,
        bcrypt_cost=10,
        smtp_security="none",
        privacy_policy_version="2026-10-06",
    )


@pytest.fixture
def engine(settings):
    engine = create_engine(settings.database_url)
    assert engine.url.database.endswith("_test"), "Use um banco exclusivo com sufixo _test"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def app(settings, engine):
    return create_app(settings, engine=engine, clock=FakeClock(), mailer=FakeMailer())


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def db(engine):
    with sessionmaker(engine)() as session:
        yield session


PASSWORD = "Senha-segura-123!"


def register(client, email="produtor@example.com", password=PASSWORD):
    return client.post(
        "/api/v1/auth/register",
        json={
            "name": "Marcos",
            "email": email,
            "password": password,
            "accepted_terms": True,
            "privacy_policy_version": "2026-10-06",
        },
    )


def signup(client, app, email="produtor@example.com"):
    result = register(client, email)
    assert result.status_code == 202, result.text
    code = app.state.mailer.verifications[-1][1]
    result = client.post(
        "/api/v1/auth/verify-email",
        json={
            "registration_token": result.json()["registration_token"],
            "code": code,
            "password": PASSWORD,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def bearer(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}
