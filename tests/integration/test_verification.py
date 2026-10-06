from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from tests.conftest import PASSWORD, register


def challenge(client, app):
    result = register(client)
    return {
        "registration_token": result.json()["registration_token"],
        "code": app.state.mailer.verifications[-1][1],
        "password": PASSWORD,
    }


@pytest.mark.parametrize("seconds,status", [(59, 201), (60, 400)])
def test_exact_expiry(client, app, seconds, status):
    data = challenge(client, app)
    app.state.clock.advance(seconds)
    assert client.post("/api/v1/auth/verify-email", json=data).status_code == status


def test_leading_zero_and_single_use(client, app):
    with patch("app.core.security.secrets.randbelow", return_value=7):
        data = challenge(client, app)
    assert data["code"] == "000007"
    assert client.post("/api/v1/auth/verify-email", json=data).status_code == 201
    assert client.post("/api/v1/auth/verify-email", json=data).status_code == 400


def test_resend_timing_and_old_code(client, app):
    with patch("app.core.security.secrets.randbelow", return_value=123456):
        data = challenge(client, app)
    payload = {"registration_token": data["registration_token"]}
    app.state.clock.advance(59)
    assert client.post("/api/v1/auth/resend-code", json=payload).status_code == 429
    app.state.clock.advance(1)
    with patch("app.core.security.secrets.randbelow", return_value=654321):
        assert client.post("/api/v1/auth/resend-code", json=payload).status_code == 202
    assert client.post("/api/v1/auth/verify-email", json=data).status_code == 400
    data["code"] = "654321"
    assert client.post("/api/v1/auth/verify-email", json=data).status_code == 201


def test_wrong_password_and_attempt_limit(client, app):
    data = challenge(client, app)
    wrong = {**data, "password": "senha incorreta"}
    for _ in range(5):
        assert client.post("/api/v1/auth/verify-email", json=wrong).status_code == 400
    app.state.clock.advance(60)
    assert (
        client.post(
            "/api/v1/auth/resend-code",
            json={
                "registration_token": data["registration_token"],
            },
        ).status_code
        == 400
    )
    assert client.post("/api/v1/auth/verify-email", json=data).status_code == 400


def test_concurrent_confirmation_consumes_once(client, app):
    data = challenge(client, app)
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(lambda _: client.post("/api/v1/auth/verify-email", json=data), range(2))
        )
    assert sorted(r.status_code for r in results) == [201, 400]
