from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, SessionRead, UserRead
from app.services.auth import AuthService, attach_session_cookie, clear_session_cookie

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=SessionRead, status_code=201)
def register(body: RegisterRequest, response: Response, session: Session = Depends(get_db)) -> SessionRead:
    user, token = AuthService(session).register(body.email, body.password, body.display_name)
    attach_session_cookie(response, token)
    return SessionRead(user=UserRead.model_validate(user))


@router.post("/login", response_model=SessionRead)
def login(body: LoginRequest, response: Response, session: Session = Depends(get_db)) -> SessionRead:
    user, token = AuthService(session).login(body.email, body.password)
    attach_session_cookie(response, token)
    return SessionRead(user=UserRead.model_validate(user))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_db)) -> Response:
    from app.core.constants import SESSION_COOKIE

    AuthService(session).logout(request.cookies.get(SESSION_COOKIE))
    clear_session_cookie(response)
    return Response(status_code=204)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
