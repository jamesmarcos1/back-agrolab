from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import register


def test_login_limit_persists_across_apps(client, app):
    payload = {"email": "missing@example.com", "password": "wrong"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=payload).status_code == 401
    other = create_app(
        app.state.settings, engine=app.state.engine, clock=app.state.clock, mailer=app.state.mailer
    )
    with TestClient(other) as second:
        result = second.post("/api/v1/auth/login", json=payload)
        assert result.status_code == 429
        assert int(result.headers["Retry-After"]) > 0
        app.state.clock.advance(901)
        assert second.post("/api/v1/auth/login", json=payload).status_code == 401


def test_email_send_limit_under_concurrency(client, app):
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _: register(client), range(6)))
    assert sum(r.status_code == 202 for r in results) == 5
    assert sum(r.status_code == 429 for r in results) == 1
    assert len(app.state.mailer.verifications) == 5


def test_untrusted_forwarded_header_does_not_bypass_limit(client):
    for i in range(31):
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
            json={"email": f"missing{i}@example.com", "password": "wrong"},
        )
    assert response.status_code == 429
