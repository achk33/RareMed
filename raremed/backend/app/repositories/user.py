import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthSession, User
from app.repositories.conversation import utcnow


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def add(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
        role: str,
        now: datetime,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def list_users(self) -> list[User]:
        return list(self.session.scalars(select(User).order_by(User.created_at.asc())).all())


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, *, user: User, token_hash: str, expires_at: datetime, now: datetime) -> AuthSession:
        item = AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return self.session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))

    def revoke(self, item: AuthSession, now: datetime | None = None) -> None:
        item.revoked_at = now or utcnow()
