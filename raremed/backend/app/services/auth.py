import logging
from datetime import timedelta

from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.constants import SESSION_COOKIE, USER_ROLES
from app.core.errors import AppError
from app.core.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    normalize_email,
    verify_password,
)
from app.models import AuthSession, User
from app.repositories.conversation import as_utc, utcnow
from app.repositories.user import SessionRepository, UserRepository

logger = logging.getLogger("raremed.auth")


class AuthService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)

    def register(self, email: str, password: str, display_name: str | None) -> tuple[User, str]:
        cleaned = normalize_email(email)
        if self.users.get_by_email(cleaned) is not None:
            raise AppError("email_taken", "An account with that email already exists.", 409)
        now = utcnow()
        local = cleaned.split("@", 1)[0]
        user = self.users.add(
            email=cleaned,
            password_hash=hash_password(password),
            display_name=(display_name or local)[:80],
            role="user",
            now=now,
        )
        token = self._open_session(user)
        self.session.commit()
        self.session.refresh(user)
        return user, token

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.users.get_by_email(normalize_email(email))
        if user is None or not verify_password(user.password_hash, password):
            raise AppError("invalid_credentials", "That email or password is not correct.", 401)
        if not user.is_active:
            raise AppError("account_disabled", "This account is disabled.", 403)
        token = self._open_session(user)
        self.session.commit()
        self.session.refresh(user)
        return user, token

    def logout(self, token: str | None) -> None:
        if not token:
            return
        item = self.sessions.get_by_token_hash(hash_session_token(token))
        if item is not None and item.revoked_at is None:
            self.sessions.revoke(item)
            self.session.commit()

    def user_for_token(self, token: str) -> User | None:
        item = self.sessions.get_by_token_hash(hash_session_token(token))
        if item is None or not _session_is_live(item):
            return None
        user = self.users.get(item.user_id)
        if user is None or not user.is_active:
            return None
        return user

    def list_users(self) -> list[User]:
        return self.users.list_users()

    def update_user(self, user_id, *, role: str | None, is_active: bool | None) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise AppError("user_not_found", "Account was not found.", 404)
        if role is not None:
            if role not in USER_ROLES:
                raise AppError("validation_error", "That role is not supported.", 422)
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        user.updated_at = utcnow()
        self.session.commit()
        self.session.refresh(user)
        return user

    def seed_admin(self) -> None:
        email = normalize_email(self.settings.admin_email)
        password = self.settings.admin_password
        if not email or not password:
            return
        existing = self.users.get_by_email(email)
        if existing is not None:
            return
        now = utcnow()
        self.users.add(
            email=email,
            password_hash=hash_password(password),
            display_name="Administrator",
            role="admin",
            now=now,
        )
        self.session.commit()

    def _open_session(self, user: User) -> str:
        token = new_session_token()
        now = utcnow()
        self.sessions.add(
            user=user,
            token_hash=hash_session_token(token),
            expires_at=now + timedelta(seconds=self.settings.session_ttl_seconds),
            now=now,
        )
        return token


def attach_session_cookie(response: Response, token: str, settings: Settings | None = None) -> None:
    config = settings or get_settings()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=config.session_cookie_secure,
        samesite=config.cookie_samesite,  # type: ignore[arg-type]
        max_age=config.session_ttl_seconds,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _session_is_live(item: AuthSession) -> bool:
    if item.revoked_at is not None:
        return False
    return as_utc(item.expires_at) > utcnow()
