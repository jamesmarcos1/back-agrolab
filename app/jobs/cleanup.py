import logging
import sys
import time
from datetime import timedelta

from sqlalchemy import delete, select, text

from app.core.config import Settings
from app.core.security import Clock
from app.db.models import (
    AuthEvent,
    AuthSession,
    DeletionRequest,
    PasswordReset,
    PendingRegistration,
    RateLimit,
    User,
)
from app.db.session import database, lock
from app.modules.auth.repository import fingerprint

logger = logging.getLogger("agrolab.cleanup")


def cleanup(factory, now, secret=None):
    # O gate segura apenas o lock global; cada entidade usa sua própria transação.
    # Nunca manter locks de usuário durante a retenção de contadores de tentativa.
    with factory() as gate:
        if not gate.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended('agrolab:cleanup', 0))")
        ):
            return 0
        removed = 0
        users = gate.execute(
            select(User.id, User.email).where(User.status == "deletion_pending")
        ).all()
        for user_id, email in users:
            with factory.begin() as db:
                lock(db, "email:" + email)
                lock(db, "user:" + user_id)
                user = db.get(User, user_id)
                if user is None or user.status != "deletion_pending":
                    continue
                db.execute(delete(PendingRegistration).where(PendingRegistration.email == email))
                if secret:
                    db.execute(
                        delete(AuthEvent).where(
                            AuthEvent.subject_hash == fingerprint(secret, email)
                        )
                    )
                db.execute(delete(DeletionRequest).where(DeletionRequest.user_id == user_id))
                db.delete(user)
                removed += 1
        pendings = gate.execute(
            select(PendingRegistration.id, PendingRegistration.email).where(
                PendingRegistration.expires_at <= now
            )
        ).all()
        for pending_id, email in pendings:
            with factory.begin() as db:
                lock(db, "email:" + email)
                lock(db, "registration:" + pending_id)
                db.execute(
                    delete(PendingRegistration).where(
                        PendingRegistration.id == pending_id, PendingRegistration.expires_at <= now
                    )
                )
        resets = gate.execute(
            select(PasswordReset.id, PasswordReset.user_id).where(PasswordReset.expires_at <= now)
        ).all()
        for reset_id, user_id in resets:
            with factory.begin() as db:
                lock(db, "user:" + user_id)
                db.execute(
                    delete(PasswordReset).where(
                        PasswordReset.id == reset_id, PasswordReset.expires_at <= now
                    )
                )
        sessions = gate.execute(
            select(AuthSession.id, AuthSession.user_id).where(AuthSession.expires_at <= now)
        ).all()
        for session_id, user_id in sessions:
            with factory.begin() as db:
                lock(db, "user:" + user_id)
                lock(db, "session:" + session_id)
                db.execute(
                    delete(AuthSession).where(
                        AuthSession.id == session_id, AuthSession.expires_at <= now
                    )
                )
        with factory.begin() as db:
            db.execute(delete(RateLimit).where(RateLimit.expires_at <= now))
            db.execute(delete(AuthEvent).where(AuthEvent.at < now - timedelta(days=14)))
        return removed


def main():
    settings = Settings()
    engine, factory = database(settings)
    try:
        while True:
            try:
                count = cleanup(factory, Clock().now(), settings.otp_secret)
                logger.info("cleanup_deleted_accounts=%s", count)
            except Exception as exc:
                logger.error("cleanup_failed_type=%s", type(exc).__name__)
                if "--loop" not in sys.argv:
                    raise
            if "--loop" not in sys.argv:
                break
            time.sleep(3600)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
