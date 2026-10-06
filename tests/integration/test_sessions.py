from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest

from tests.conftest import PASSWORD, bearer, signup


def test_login_and_user_isolation(client, app):
    first = signup(client, app)
    second = signup(client, app, "outro@example.com")
    for tokens in [first, second]:
        result = client.get("/api/v1/users/me", headers=bearer(tokens))
        assert result.status_code == 200
        assert result.json()["id"] == tokens["user"]["id"]
    assert first["user"]["id"] != second["user"]["id"]
    result = client.post(
        "/api/v1/auth/login", json={"email": "produtor@example.com", "password": PASSWORD}
    )
    assert result.status_code == 200
    assert "password" not in result.text


def test_invalid_credentials_same_response(client, app):
    signup(client, app)
    responses = [
        client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        for email in ["produtor@example.com", "missing@example.com"]
    ]
    assert all(r.status_code == 401 for r in responses)
    assert responses[0].json()["error"]["code"] == responses[1].json()["error"]["code"]
    assert responses[0].json()["error"]["message"] == responses[1].json()["error"]["message"]


def test_logout_revokes_access_and_refresh(client, app):
    tokens = signup(client, app)
    payload = {"refresh_token": tokens["refresh_token"]}
    assert client.post("/api/v1/auth/logout", json=payload).status_code == 204
    assert client.get("/api/v1/users/me", headers=bearer(tokens)).status_code == 401
    assert client.post("/api/v1/auth/refresh", json=payload).status_code == 401
    assert client.post("/api/v1/auth/logout", json=payload).status_code == 204


def test_refresh_rotates_and_replay_revokes_family(client, app):
    tokens = signup(client, app)
    payload = {"refresh_token": tokens["refresh_token"]}
    fresh = client.post("/api/v1/auth/refresh", json=payload)
    assert fresh.status_code == 200
    assert fresh.json()["refresh_token"] != tokens["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json=payload).status_code == 401
    assert client.get("/api/v1/users/me", headers=bearer(fresh.json())).status_code == 401


def test_concurrent_refresh_has_one_winner(client, app):
    tokens = signup(client, app)
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda _: client.post(
                    "/api/v1/auth/refresh",
                    json={
                        "refresh_token": tokens["refresh_token"],
                    },
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in results) == [200, 401]
    winner = next(r.json() for r in results if r.status_code == 200)
    assert client.get("/api/v1/users/me", headers=bearer(winner)).status_code == 401


@pytest.mark.parametrize("change", ["aud", "iss", "exp", "signature"])
def test_reject_invalid_jwt(client, app, change):
    tokens = signup(client, app)
    settings = app.state.settings
    claims = jwt.decode(
        tokens["access_token"],
        settings.jwt_secret,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    key = settings.jwt_secret
    if change == "exp":
        claims["exp"] = 0
    elif change == "signature":
        key = "other-secret-" + "c" * 64
    else:
        claims[change] = "other-environment"
    tokens["access_token"] = jwt.encode(claims, key, algorithm="HS256")
    assert client.get("/api/v1/users/me", headers=bearer(tokens)).status_code == 401


def test_expiry_and_absolute_refresh_lifetime(client, app):
    tokens = signup(client, app)
    app.state.clock.advance(900)
    assert client.get("/api/v1/users/me", headers=bearer(tokens)).status_code == 401
    fresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert fresh.status_code == 200
    app.state.clock.advance(7 * 86400)
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": fresh.json()["refresh_token"]}
        ).status_code
        == 401
    )
