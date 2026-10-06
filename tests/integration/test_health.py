from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings


def test_health(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_readiness_without_database(client, app):
    with patch.object(app.state.engine, "connect", side_effect=OperationalError("", {}, None)):
        assert client.get("/health/ready").status_code == 503


def test_production_rejects_insecure_configuration():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="sqlite:///x",
            jwt_secret="CHANGE_ME",
            otp_secret="CHANGE_ME",
        )


def test_validation_never_echoes_password(client):
    response = client.post("/api/v1/auth/login", json={"email": "bad", "password": "secret"})
    assert response.status_code == 422
    assert "secret" not in response.text
    assert response.json()["error"]["request_id"]


def test_openapi_marks_authenticated_profile(app):
    contract = app.openapi()
    assert contract["paths"]["/api/v1/users/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert contract["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
