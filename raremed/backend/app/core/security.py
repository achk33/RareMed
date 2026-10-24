"""Password hashes and opaque session tokens.

The raw session token is sent only in an HTTP-only cookie. The database stores
a SHA-256 digest of that token.
"""

import hashlib
import secrets

from argon2 import PasswordHasher

hasher = PasswordHasher()
SESSION_COOKIE = "raremed_session"


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except Exception:
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()
