"""FastAPI dependencies for authentication and per-site authorization.

Authorization is enforced SERVER-SIDE for every site-scoped route: the
authenticated manager's ``site_id`` must match the site requested in the path
or query string, unless the manager has the ``admin`` role. The frontend hides
the login screen, but every one of these checks still runs on the backend, so
the UI can never be bypassed by hand-editing requests.
"""

from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.auth.security import decode_access_token
from app.models.models import Manager

_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_manager(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Manager:
    """Resolve the authenticated manager from the Authorization header.

    A ``?token=`` query-param fallback is accepted because browser media
    elements (``<img>`` MJPEG streams) cannot attach an Authorization header.
    """
    raw = credentials.credentials if credentials is not None else request.query_params.get("token")
    if not raw:
        raise _CREDENTIALS_EXC
    try:
        payload = decode_access_token(raw)
    except jwt.PyJWTError:
        raise _CREDENTIALS_EXC

    manager = db.query(Manager).filter(Manager.id == payload.get("sub")).first()
    if manager is None or not manager.is_active:
        raise _CREDENTIALS_EXC
    # Token was issued at a previous token_version -> logged out server-side.
    if payload.get("ver") != manager.token_version:
        raise _CREDENTIALS_EXC
    return manager


def require_auth(manager: Manager = Depends(get_current_manager)) -> Manager:
    """Marker dependency: enforces authentication on an entire router."""
    return manager


def authorize_site(manager: Manager | None, site_id: str | None) -> None:
    """Verify a manager may access ``site_id``; raise 403 when not allowed."""
    if site_id is None:
        return
    if manager.role == "admin":
        return
    if manager.site_id != site_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: manager is not authorized for this site",
        )


def require_site_access(
    request: Request,
    manager: Manager = Depends(get_current_manager),
) -> Manager:
    """Auth + site-scoped authorization derived from path/query site_id."""
    site_id = request.path_params.get("site_id")
    if site_id is None:
        site_id = request.query_params.get("site_id")
    authorize_site(manager, site_id)
    return manager


def ws_get_manager(db: Session, token: str | None) -> Optional[Manager]:
    """Authenticate a WebSocket handshake from its ``?token=`` query param."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None

    manager = db.query(Manager).filter(Manager.id == payload.get("sub")).first()
    if manager is None or not manager.is_active:
        return None
    if payload.get("ver") != manager.token_version:
        return None
    return manager