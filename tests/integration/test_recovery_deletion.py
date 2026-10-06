from sqlalchemy import func, select

from app.db.models import User
from app.jobs.cleanup import cleanup
from tests.conftest import PASSWORD, bearer, signup


def test_password_reset_single_use_revokes_sessions(client, app):
    tokens = signup(client, app)
    known = client.post("/api/v1/auth/forgot-password", json={"email": "produtor@example.com"})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    token = app.state.mailer.resets[-1][1]
    payload = {"reset_token": token, "new_password": "Nova-senha-123!"}
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 204
    assert client.get("/api/v1/users/me", headers=bearer(tokens)).status_code == 401
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "produtor@example.com",
                "password": "Nova-senha-123!",
            },
        ).status_code
        == 200
    )


def test_reset_expired(client, app):
    signup(client, app)
    client.post("/api/v1/auth/forgot-password", json={"email": "produtor@example.com"})
    token = app.state.mailer.resets[-1][1]
    app.state.clock.advance(900)
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={
                "reset_token": token,
                "new_password": "Nova-senha-123!",
            },
        ).status_code
        == 400
    )


def test_account_deletion_revokes_and_purges(client, app, db):
    tokens = signup(client, app)
    assert (
        client.request(
            "DELETE", "/api/v1/users/me", headers=bearer(tokens), json={"password": "wrong"}
        ).status_code
        == 401
    )
    response = client.request(
        "DELETE", "/api/v1/users/me", headers=bearer(tokens), json={"password": PASSWORD}
    )
    assert response.status_code == 202
    assert client.get("/api/v1/users/me", headers=bearer(tokens)).status_code == 401
    cleanup(app.state.session_factory, app.state.clock.now())
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert cleanup(app.state.session_factory, app.state.clock.now()) == 0
