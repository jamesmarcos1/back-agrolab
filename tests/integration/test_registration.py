from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.db.models import User
from tests.conftest import PASSWORD, bearer, register, signup


def test_registration_requires_confirmation(client, app, db):
    result = register(client)
    assert result.status_code == 202
    assert result.json()["expires_in"] == 60
    assert len(app.state.mailer.verifications[-1][1]) == 6
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "produtor@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"email": "invalid"},
        {"password": "short"},
        {"password": "é" * 40},
        {"accepted_terms": False},
        {"privacy_policy_version": "old"},
    ],
)
def test_invalid_registration(client, changes):
    payload = {
        "name": "Marcos",
        "email": "produtor@example.com",
        "password": PASSWORD,
        "accepted_terms": True,
        "privacy_policy_version": "2026-10-06",
    }
    payload.update(changes)
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422


def test_duplicate_does_not_modify_account(client, app, db):
    first = signup(client, app)
    result = register(client, "PRODUTOR@example.com", "Senha-outra-123!")
    assert result.status_code == 202
    assert len(app.state.mailer.verifications) == 1
    assert db.scalar(select(func.count()).select_from(User)) == 1
    assert client.get("/api/v1/users/me", headers=bearer(first)).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "PRODUTOR@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )


def test_email_failure_never_activates_account(client, app, db):
    app.state.mailer.fail = True
    assert register(client).status_code == 202
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_concurrent_signup_for_same_email(client, app, db):
    results = [register(client), register(client)]
    requests = [
        {
            "registration_token": r.json()["registration_token"],
            "code": code[1],
            "password": PASSWORD,
        }
        for r, code in zip(results, app.state.mailer.verifications, strict=True)
    ]
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(lambda data: client.post("/api/v1/auth/verify-email", json=data), requests)
        )
    assert sorted(r.status_code for r in responses) == [201, 400]
    assert db.scalar(select(func.count()).select_from(User)) == 1
