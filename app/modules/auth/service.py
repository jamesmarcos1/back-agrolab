import hmac
import logging
from datetime import timedelta

from sqlalchemy import select, update

from app.core.errors import APIError, invalid_code, invalid_credentials, invalid_session
from app.core.security import (
    check_password,
    code_digest,
    decode_access,
    encode_access,
    generate_code,
    hash_password,
    random_token,
    token_hash,
)
from app.db.models import (
    AuthEvent,
    AuthSession,
    DeletionRequest,
    PasswordReset,
    PendingRegistration,
    RefreshToken,
    User,
    VerificationChallenge,
)
from app.db.session import lock
from app.modules.auth.repository import check_limit, consume_limit, fingerprint

logger = logging.getLogger("agrolab.auth")


def user_output(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
    }


class AuthService:
    def __init__(self, db, request):
        self.db = db
        self.request = request
        self.state = request.app.state
        self.settings = self.state.settings
        self.ip = request.client.host if request.client else "unknown"

    @property
    def now(self):
        return self.state.clock.now()

    def reload(self, model, row_id):
        return self.db.scalar(
            select(model).where(model.id == row_id).execution_options(populate_existing=True)
        )

    def verification_mail(self, email, code):
        try:
            self.mail(lambda: self.state.mailer.send_verification(email, code, 60))
        except APIError:
            # 202 confirma a criação do desafio, não a entrega do e-mail.
            # Falha não pode distinguir conta existente de cadastro novo.
            pass

    def event(self, kind, subject=None, session_id=None):
        self.db.add(
            AuthEvent(
                event=kind,
                at=self.now,
                request_id=self.request.state.request_id,
                session_id=session_id,
                subject_hash=fingerprint(self.settings.otp_secret, subject) if subject else None,
            )
        )
        logger.info(
            "event=%s request_id=%s session_id=%s",
            kind,
            self.request.state.request_id,
            session_id or "none",
        )

    def limit(self, key, seconds, maximum):
        consume_limit(self.db, self.settings.otp_secret, key, self.now, seconds, maximum)

    def send_limits(self, email):
        self.limit("mail:ip:" + self.ip, 3600, 20)
        self.limit("mail:email:" + email, 3600, 5)

    def mail(self, operation):
        try:
            operation()
        except (OSError, ValueError) as exc:
            self.event("email_delivery_failed")
            # Não incluir mensagens SMTP, que podem conter destinatário ou credenciais.
            logger.warning("email_failure_type=%s", type(exc).__name__)
            raise APIError(
                503, "EMAIL_UNAVAILABLE", "Não foi possível enviar o e-mail. Tente novamente."
            ) from None

    def create_session(self, user):
        now = self.now
        session = AuthSession(
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(seconds=self.settings.session_seconds),
        )
        self.db.add(session)
        self.db.flush()
        return self.issue_tokens(user, session)

    def issue_tokens(self, user, session):
        refresh = random_token()
        self.db.add(
            RefreshToken(session_id=session.id, token_hash=token_hash(refresh), created_at=self.now)
        )
        return {
            "access_token": encode_access(self.settings, user.id, session.id, self.now),
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": self.settings.access_seconds,
            "user": user_output(user),
        }

    def register(self, data):
        if data.privacy_policy_version != self.settings.privacy_policy_version:
            raise APIError(
                422,
                "POLICY_VERSION_INVALID",
                "Atualize a política de privacidade antes de cadastrar.",
            )
        lock(self.db, "email:" + data.email)
        self.send_limits(data.email)
        existing = self.db.scalar(select(User).where(User.email == data.email))
        token = random_token()
        pending = PendingRegistration(
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password, self.settings.bcrypt_cost),
            token_hash=token_hash(token),
            inert=existing is not None,
            privacy_policy_version=data.privacy_policy_version,
            created_at=self.now,
            expires_at=self.now + timedelta(hours=24),
        )
        self.db.add(pending)
        self.db.flush()
        code = generate_code()
        self.db.add(
            VerificationChallenge(
                registration_id=pending.id,
                code_digest=code_digest(self.settings.otp_secret, pending.id, code),
                expires_at=self.now + timedelta(seconds=60),
                last_sent_at=self.now,
            )
        )
        if not pending.inert:
            self.verification_mail(data.email, code)
        self.event("registration_requested", data.email)
        return {"registration_token": token, "expires_in": 60, "resend_after": 60}

    def registration(self, token):
        self.limit("verify:ip:" + self.ip, 900, 60)
        pending = self.db.scalar(
            select(PendingRegistration).where(PendingRegistration.token_hash == token_hash(token))
        )
        if pending is None:
            self.event("verification_denied")
            raise invalid_code()
        lock(self.db, "email:" + pending.email)
        lock(self.db, "registration:" + pending.id)
        pending = self.reload(PendingRegistration, pending.id)
        if pending is None:
            self.event("verification_denied")
            raise invalid_code()
        challenge = self.db.scalar(
            select(VerificationChallenge).where(VerificationChallenge.registration_id == pending.id)
        )
        if (
            not challenge
            or pending.consumed_at
            or self.now >= pending.expires_at
            or challenge.attempts >= 5
        ):
            self.event("verification_denied", pending.email)
            raise invalid_code()
        return pending, challenge

    def verify(self, data):
        pending, challenge = self.registration(data.registration_token)
        valid = (
            not pending.inert
            and not challenge.consumed_at
            and self.now < challenge.expires_at
            and hmac.compare_digest(
                challenge.code_digest, code_digest(self.settings.otp_secret, pending.id, data.code)
            )
            and check_password(data.password, pending.password_hash)
        )
        existing = self.db.scalar(select(User).where(User.email == pending.email))
        if not valid or existing:
            challenge.attempts += 1
            self.event("verification_denied", pending.email)
            raise invalid_code()
        now = self.now
        user = User(
            name=pending.name,
            email=pending.email,
            password_hash=pending.password_hash,
            email_verified_at=now,
            privacy_policy_version=pending.privacy_policy_version,
            terms_accepted_at=pending.created_at,
            created_at=now,
            updated_at=now,
        )
        challenge.consumed_at = now
        pending.consumed_at = now
        self.db.add(user)
        self.db.flush()
        tokens = self.create_session(user)
        self.event("registration_verified", user.email)
        return tokens

    def resend(self, data):
        pending, challenge = self.registration(data.registration_token)
        remaining = 60 - (self.now - challenge.last_sent_at).total_seconds()
        if remaining > 0:
            raise APIError(
                429, "RESEND_TOO_EARLY", "Aguarde antes de reenviar o código.", int(remaining) + 1
            )
        self.send_limits(pending.email)
        code = generate_code()
        challenge.code_digest = code_digest(self.settings.otp_secret, pending.id, code)
        challenge.expires_at = self.now + timedelta(seconds=60)
        challenge.last_sent_at = self.now
        if not pending.inert:
            self.verification_mail(pending.email, code)
        self.event("verification_resent", pending.email)
        return {"registration_token": data.registration_token, "expires_in": 60, "resend_after": 60}

    def login(self, data):
        self.limit("login:ip:" + self.ip, 900, 30)
        lock(self.db, "login:" + data.email)
        check_limit(self.db, self.settings.otp_secret, "login:fail:" + data.email, self.now, 900, 5)
        user = self.db.scalar(select(User).where(User.email == data.email))
        if user:
            lock(self.db, "user:" + user.id)
            user = self.reload(User, user.id)
        password_hash = user.password_hash if user else self.state.dummy_hash
        valid = check_password(data.password, password_hash)
        if not valid or not user or user.status != "active":
            self.limit("login:fail:" + data.email, 900, 1000)
            self.event("login_denied", data.email)
            raise invalid_credentials()
        self.event("login_succeeded", user.email)
        return self.create_session(user)

    def session_from_refresh(self, token):
        row = self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash(token))
        )
        if row is None:
            self.event("refresh_denied")
            raise invalid_session()
        session = self.db.get(AuthSession, row.session_id)
        if session is None:
            raise invalid_session()
        lock(self.db, "user:" + session.user_id)
        lock(self.db, "session:" + session.id)
        session = self.reload(AuthSession, session.id)
        row = self.reload(RefreshToken, row.id)
        if session is None or row is None:
            raise invalid_session()
        user = self.db.get(User, session.user_id, populate_existing=True)
        if (
            session.revoked_at
            or self.now >= session.expires_at
            or not user
            or user.status != "active"
        ):
            self.event("refresh_denied", session_id=session.id)
            raise invalid_session()
        return user, session, row

    def refresh(self, data):
        self.limit("refresh:ip:" + self.ip, 900, 120)
        user, session, row = self.session_from_refresh(data.refresh_token)
        if row.consumed_at:
            session.revoked_at = self.now
            self.event("refresh_replayed", session_id=session.id)
            raise invalid_session()
        row.consumed_at = self.now
        self.event("session_refreshed", session_id=session.id)
        return self.issue_tokens(user, session)

    def logout(self, data):
        self.limit("logout:ip:" + self.ip, 900, 120)
        row = self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash(data.refresh_token))
        )
        if row:
            session = self.db.get(AuthSession, row.session_id)
            if session is None:
                return
            lock(self.db, "user:" + session.user_id)
            lock(self.db, "session:" + session.id)
            session = self.reload(AuthSession, session.id)
            if session and not session.revoked_at:
                session.revoked_at = self.now
                self.event("session_revoked", session_id=session.id)

    def authenticate(self):
        authorization = self.request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        try:
            if scheme.lower() != "bearer" or not token:
                raise invalid_session()
            claims = decode_access(self.settings, token, self.now)
            lock(self.db, "user:" + claims["sub"])
            session = self.db.get(AuthSession, claims["sid"])
            user = self.db.get(User, claims["sub"])
            if (
                not user
                or user.status != "active"
                or not session
                or session.user_id != user.id
                or session.revoked_at
                or self.now >= session.expires_at
            ):
                raise invalid_session()
            return user
        except APIError:
            self.event("access_denied")
            raise

    def forgot(self, data):
        user = self.db.scalar(select(User).where(User.email == data.email, User.status == "active"))
        if user:
            lock(self.db, "user:" + user.id)
            user = self.reload(User, user.id)
        self.send_limits(data.email)
        if user and user.status == "active":
            self.db.execute(
                update(PasswordReset)
                .where(PasswordReset.user_id == user.id, PasswordReset.consumed_at.is_(None))
                .values(consumed_at=self.now)
            )
            token = random_token()
            self.db.add(
                PasswordReset(
                    user_id=user.id,
                    token_hash=token_hash(token),
                    expires_at=self.now + timedelta(minutes=15),
                )
            )
            try:
                self.mail(lambda: self.state.mailer.send_password_reset(data.email, token))
            except APIError:
                # Resposta idêntica para conta existente/ausente, inclusive se SMTP falhar.
                pass
        self.event("password_reset_requested", data.email)
        return {
            "message": "Se houver uma conta para este e-mail, enviaremos instruções de recuperação."
        }

    def reset(self, data):
        self.limit("reset:ip:" + self.ip, 900, 30)
        row = self.db.scalar(
            select(PasswordReset).where(PasswordReset.token_hash == token_hash(data.reset_token))
        )
        if not row:
            raise invalid_code()
        lock(self.db, "user:" + row.user_id)
        row = self.reload(PasswordReset, row.id)
        if row is None:
            raise invalid_code()
        user = self.db.get(User, row.user_id)
        if row.consumed_at or self.now >= row.expires_at or not user or user.status != "active":
            raise invalid_code()
        row.consumed_at = self.now
        user.password_hash = hash_password(data.new_password, self.settings.bcrypt_cost)
        user.updated_at = self.now
        self.revoke_user(user)
        self.db.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user.id)
            .values(consumed_at=self.now)
        )
        self.event("password_reset_completed", user.email)

    def revoke_user(self, user):
        self.db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=self.now)
        )

    def delete_account(self, data):
        user = self.authenticate()
        self.limit("delete:" + user.id, 900, 5)
        if not check_password(data.password, user.password_hash):
            self.event("deletion_denied", user.email)
            raise invalid_credentials()
        user.status = "deletion_pending"
        user.updated_at = self.now
        self.revoke_user(user)
        self.db.add(DeletionRequest(user_id=user.id, requested_at=self.now))
        self.event("deletion_requested", user.email)
        return {"message": "Conta encerrada. A exclusão dos dados foi solicitada."}


def perform(db, request, action):
    """Persistir também erros esperados: tentativas e revogações não podem sofrer rollback."""
    service = AuthService(db, request)
    try:
        result = action(service)
        db.commit()
        return result
    except APIError:
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise
