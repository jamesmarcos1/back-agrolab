import hashlib
import hmac
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import APIError
from app.db.models import RateLimit


def fingerprint(secret: str, value: str):
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def consume_limit(db, secret, key, now, seconds, maximum):
    bucket = int(now.timestamp()) // seconds * seconds
    digest = fingerprint(secret, key)
    expires = datetime.fromtimestamp(bucket + seconds, UTC)
    statement = insert(RateLimit).values(
        key=digest, window_start=bucket, count=1, expires_at=expires
    )
    statement = statement.on_conflict_do_update(
        index_elements=[RateLimit.key, RateLimit.window_start],
        set_={"count": RateLimit.count + 1},
    ).returning(RateLimit.count)
    count = db.scalar(statement)
    if count > maximum:
        raise APIError(
            429,
            "RATE_LIMITED",
            "Muitas tentativas. Aguarde antes de tentar novamente.",
            max(1, int((expires - now).total_seconds()) + 1),
        )


def check_limit(db, secret, key, now, seconds, maximum):
    bucket = int(now.timestamp()) // seconds * seconds
    row = db.scalar(
        select(RateLimit).where(
            RateLimit.key == fingerprint(secret, key), RateLimit.window_start == bucket
        )
    )
    if row and row.count >= maximum:
        raise APIError(
            429,
            "RATE_LIMITED",
            "Muitas tentativas. Aguarde antes de tentar novamente.",
            max(1, int((row.expires_at - now).total_seconds()) + 1),
        )
