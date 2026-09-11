"""Password hashing (stdlib scrypt) and JWT access tokens.

No third-party crypto dependency is required: passwords are hashed with
``hashlib.scrypt`` (a memory-hard KDF) using a per-user random salt, and tokens
are signed HS256 JWTs carrying the manager's token version so server-side
logout can invalidate all outstanding tokens.

Storage format for password hashes: ``scrypt$N$R$P$salt_hex$digest_hex``.
Keys and secrets always come from environment configuration (``app.config``) —
never from code.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_DIGEST_BYTES = 32


def hash_password(password: str) -> str:
    """Hash ``password`` with scrypt + a fresh random salt."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DIGEST_BYTES,
    )
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        salt.hex(),
        digest.hex(),
    )


def verify_password(password: str, hashed: str) -> bool:
    """Recompute the scrypt digest and compare in constant time."""
    try:
        scheme, n_s, r_s, p_s, salt_hex, digest_hex = hashed.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    token_version: int,
    expires_minutes: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Issue a signed HS256 JWT for a manager, keyed to their token version."""
    now = datetime.now(timezone.utc)
    minutes = expires_minutes if expires_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    payload: dict[str, Any] = {
        "sub": subject,
        "ver": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` when invalid/expired."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])