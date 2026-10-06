import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from app.db.models import PasswordReset, User
from app.jobs import cleanup as cleanup_module
from app.jobs.cleanup import cleanup
from app.modules.auth import service
from tests.conftest import PASSWORD, bearer, register, signup


def test_smtp_failure_does_not_reveal_existing_account(client, app):
    signup(client, app)
    app.state.mailer.fail = True
    existing = register(client)
    unknown = register(client, "new@example.com")
    assert existing.status_code == unknown.status_code == 202
    assert set(existing.json()) == set(unknown.json())
    app.state.clock.advance(60)
    for response in [existing, unknown]:
        result = client.post(
            "/api/v1/auth/resend-code",
            json={
                "registration_token": response.json()["registration_token"],
            },
        )
        assert result.status_code == 202


def test_register_and_resend_share_lock_order(client, app, monkeypatch):
    token = register(client).json()["registration_token"]
    app.state.clock.advance(60)
    mail_locked = threading.Event()
    resend_locked = threading.Event()
    local = threading.local()
    original_lock = service.lock
    original_limits = service.AuthService.send_limits
    original_registration = service.AuthService.registration

    def tracked_lock(db, key):
        original_lock(db, key)
        if key.startswith("email:"):
            local.email_locked = True
            if getattr(local, "action", None) == "resend":
                resend_locked.set()

    def tracked_limits(self, email):
        if self.request.url.path.endswith("/register"):
            local.action = "register"
        original_limits(self, email)
        if getattr(local, "action", None) == "register":
            mail_locked.set()
            if not getattr(local, "email_locked", False):
                assert resend_locked.wait(5)

    def tracked_registration(self, token):
        local.action = "resend"
        return original_registration(self, token)

    monkeypatch.setattr(service, "lock", tracked_lock)
    monkeypatch.setattr(service.AuthService, "send_limits", tracked_limits)
    monkeypatch.setattr(service.AuthService, "registration", tracked_registration)

    def registering():
        local.action = "register"
        return register(client)

    def resending():
        local.action = "resend"
        assert mail_locked.wait(5)
        return client.post("/api/v1/auth/resend-code", json={"registration_token": token})

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(registering)
        second = pool.submit(resending)
        assert first.result().status_code == second.result().status_code == 202


def cleanup_before_lock(app, monkeypatch):
    original = service.lock
    done = False

    def hooked(db, key):
        nonlocal done
        if not done:
            done = True
            cleanup(app.state.session_factory, app.state.clock.now(), app.state.settings.otp_secret)
        return original(db, key)

    monkeypatch.setattr(service, "lock", hooked)


def test_cleanup_during_verification_is_invalid_code(client, app, monkeypatch):
    token = register(client).json()["registration_token"]
    code = app.state.mailer.verifications[-1][1]
    app.state.clock.advance(86400)
    cleanup_before_lock(app, monkeypatch)
    response = client.post(
        "/api/v1/auth/verify-email",
        json={
            "registration_token": token,
            "code": code,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 400


def test_cleanup_during_reset_is_invalid_code(client, app, monkeypatch):
    signup(client, app)
    client.post("/api/v1/auth/forgot-password", json={"email": "produtor@example.com"})
    token = app.state.mailer.resets[-1][1]
    app.state.clock.advance(900)
    cleanup_before_lock(app, monkeypatch)
    response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": token,
            "new_password": "Nova-senha-123!",
        },
    )
    assert response.status_code == 400


def test_cleanup_during_refresh_is_invalid_session(client, app, monkeypatch):
    tokens = signup(client, app)
    app.state.clock.advance(604800)
    cleanup_before_lock(app, monkeypatch)
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401


def test_cleanup_during_logout_remains_idempotent(client, app, monkeypatch):
    tokens = signup(client, app)
    app.state.clock.advance(604800)
    cleanup_before_lock(app, monkeypatch)
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 204
    )


def test_cleanup_during_login_is_invalid_credentials(client, app, monkeypatch):
    tokens = signup(client, app)
    with app.state.session_factory() as db:
        user = db.get(User, tokens["user"]["id"])
        user.status = "deletion_pending"
        db.commit()
    cleanup_before_lock(app, monkeypatch)
    response = client.post(
        "/api/v1/auth/login", json={"email": "produtor@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_cleanup_during_access_is_invalid_session(client, app, monkeypatch):
    tokens = signup(client, app)
    with app.state.session_factory() as db:
        user = db.get(User, tokens["user"]["id"])
        user.status = "deletion_pending"
        db.commit()
    cleanup_before_lock(app, monkeypatch)
    assert client.get("/api/v1/users/me", headers=bearer(tokens)).status_code == 401


def test_cleanup_rate_retention_does_not_deadlock_at_window_boundary(client, app, monkeypatch):
    app.state.clock.value = app.state.clock.value.replace(minute=14, second=59)
    tokens = signup(client, app)
    tokens = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()
    with app.state.session_factory() as db:
        db.add(
            PasswordReset(
                user_id=tokens["user"]["id"],
                token_hash="f" * 64,
                expires_at=app.state.clock.now() + timedelta(seconds=1),
            )
        )
        db.commit()
    rate_locked = threading.Event()
    user_locked = threading.Event()
    original_limit = service.AuthService.limit
    original_cleanup_lock = cleanup_module.lock

    def tracked_limit(self, key, seconds, maximum):
        original_limit(self, key, seconds, maximum)
        if key.startswith("refresh:"):
            rate_locked.set()
            assert user_locked.wait(5)

    def tracked_cleanup_lock(db, key):
        original_cleanup_lock(db, key)
        if key.startswith("user:"):
            user_locked.set()

    monkeypatch.setattr(service.AuthService, "limit", tracked_limit)
    monkeypatch.setattr(cleanup_module, "lock", tracked_cleanup_lock)

    def cleaning():
        assert rate_locked.wait(5)
        app.state.clock.advance(1)
        return cleanup_module.cleanup(
            app.state.session_factory, app.state.clock.now(), app.state.settings.otp_secret
        )

    with ThreadPoolExecutor(2) as pool:
        request = pool.submit(
            client.post, "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        job = pool.submit(cleaning)
        assert request.result().status_code == 200
        assert job.result() == 0
