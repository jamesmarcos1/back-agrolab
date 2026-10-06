import hashlib
import hmac
import secrets
from datetime import UTC, datetime

import bcrypt
import jwt

from app.core.errors import invalid_session


class Clock:
    def now(self):
        return datetime.now(UTC)


def random_token():
    return secrets.token_urlsafe(32)


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def code_digest(secret: str, registration_id: str, code: str):
    return hmac.new(
        secret.encode(), f"{registration_id}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def generate_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_password(password: str, cost: int):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=cost)).decode()


def check_password(password: str, password_hash: str):
    if len(password.encode()) > 72:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def encode_access(settings, user_id: str, session_id: str, now):
    claims = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + settings.access_seconds,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access(settings, token: str, now):
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": ["sub", "sid", "iat", "exp", "iss", "aud"],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
        # Mesmo relógio da sessão e OTP; permite testar fronteiras sem dormir.
        if not isinstance(claims["exp"], int) or not isinstance(claims["iat"], int):
            raise ValueError("invalid timestamp")
        if now.timestamp() >= claims["exp"] or claims["iat"] > now.timestamp() + 5:
            raise ValueError("expired or future token")
        return claims
    except (jwt.PyJWTError, ValueError, TypeError):
        raise invalid_session() from None
