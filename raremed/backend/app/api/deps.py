"""HTTP session and authorization dependencies."""

from collections.abc import Callable, Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.constants import SESSION_COOKIE, STAFF_ROLES
from app.core.database import get_session_factory
from app.core.errors import AppError
from app.models import User
from app.services.auth import AuthService


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(request: Request, session: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AppError("unauthenticated", "Sign in to continue.", 401)
    user = AuthService(session).user_for_token(token)
    if user is None:
        raise AppError("unauthenticated", "Sign in to continue.", 401)
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError("forbidden", "You do not have access to this area.", 403)
        return user

    return dependency


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in STAFF_ROLES:
        raise AppError("forbidden", "You do not have access to this area.", 403)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError("forbidden", "You do not have access to this area.", 403)
    return user
