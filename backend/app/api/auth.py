"""Manager authentication endpoints: login / me / logout (Milestone 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_manager, require_auth
from app.auth.security import create_access_token, verify_password
from app.database.database import get_db
from app.models.models import Manager
from app.services.rate_limit import clear_failures, is_blocked, record_failure

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ManagerPublic(BaseModel):
    id: str
    name: str
    email: str
    role: str
    site_id: str | None = None

    @classmethod
    def from_manager(cls, m: Manager) -> "ManagerPublic":
        return cls(id=m.id, name=m.name, email=m.email, role=m.role, site_id=m.site_id)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    manager: ManagerPublic


def _raise_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )


def authenticate(db: Session, email: str, password: str) -> Manager:
    """Verify credentials; raise 401 for unknown/inactive/wrong password.

    The response is identical for every failure mode so nothing leaks which
    part of the login was wrong.
    """
    manager = db.query(Manager).filter(Manager.email == email.strip().lower()).first()
    if manager is None or not manager.is_active:
        raise _raise_credentials()
    if not verify_password(password, manager.password_hash):
        raise _raise_credentials()
    return manager


def _client_key(request: Request) -> str:
    """Per-IP limiter key. In-process: single worker deployments only."""
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _client_key(request)
    if is_blocked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait and try again.",
        )
    try:
        manager = authenticate(db, body.email, body.password)
    except HTTPException:
        record_failure(key)
        raise
    clear_failures(key)
    token = create_access_token(
        subject=manager.id,
        token_version=manager.token_version,
        extra={"site_id": manager.site_id, "role": manager.role},
    )
    return LoginResponse(
        access_token=token,
        manager=ManagerPublic.from_manager(manager),
    )


@router.get("/me", response_model=ManagerPublic)
def me(manager: Manager = Depends(require_auth)):
    return ManagerPublic.from_manager(manager)


@router.post("/logout", response_model=dict)
def logout(manager: Manager = Depends(require_auth), db: Session = Depends(get_db)):
    """Bump the token version so every existing JWT for this manager is invalid."""
    manager.token_version += 1
    db.commit()
    return {"detail": "logged out"}