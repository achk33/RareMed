import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import User
from app.schemas.auth import UserRead, UserRoleUpdate
from app.services.auth import AuthService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> list[UserRead]:
    return [UserRead.model_validate(item) for item in AuthService(session).list_users()]


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    _: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> UserRead:
    user = AuthService(session).update_user(user_id, role=body.role, is_active=body.is_active)
    return UserRead.model_validate(user)
