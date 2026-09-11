"""Authenticated notification inbox endpoints (Milestone 4).

A manager only ever sees notifications addressed to their own account, and any
``site_id`` filter is server-side authorized against the manager's assignment.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_manager, require_auth
from app.auth.deps import authorize_site
from app.database.database import get_db
from app.models.models import Manager, Notification

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationOut(BaseModel):
    id: str
    site_id: str
    analysis_id: str | None = None
    type: str
    severity: str
    title: str
    message: str
    source: str
    risk_score: float | None = None
    status: str
    evidence: dict
    created_at: datetime | None = None
    read_at: datetime | None = None

    class Config:
        from_attributes = True


def _as_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        site_id=n.site_id,
        analysis_id=n.analysis_id,
        type=n.type,
        severity=n.severity,
        title=n.title,
        message=n.message,
        source=n.source,
        risk_score=n.risk_score,
        status=n.status,
        evidence=n.evidence if isinstance(n.evidence, dict) else {},
        created_at=n.created_at,
        read_at=n.read_at,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    status: str = "",
    severity: str = "",
    site_id: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
    manager: Manager = Depends(require_auth),
):
    authorize_site(manager, site_id or None)
    q = db.query(Notification).filter(Notification.manager_id == manager.id)
    if status:
        q = q.filter(Notification.status == status)
    if severity:
        q = q.filter(Notification.severity == severity.upper())
    if site_id:
        q = q.filter(Notification.site_id == site_id)
    rows = q.order_by(Notification.created_at.desc()).limit(min(limit, 200)).all()
    return [_as_out(n) for n in rows]


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), manager: Manager = Depends(require_auth)):
    count = (
        db.query(Notification)
        .filter(Notification.manager_id == manager.id, Notification.status == "unread")
        .count()
    )
    return {"count": count}


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str, db: Session = Depends(get_db), manager: Manager = Depends(require_auth)):
    n = (
        db.query(Notification)
        .filter(Notification.manager_id == manager.id, Notification.id == notification_id)
        .first()
    )
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.status = "read"
    n.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(n)
    return _as_out(n)


@router.patch("/read-all")
def mark_all_read(site_id: str = "", db: Session = Depends(get_db), manager: Manager = Depends(require_auth)):
    authorize_site(manager, site_id or None)
    q = db.query(Notification).filter(
        Notification.manager_id == manager.id,
        Notification.status == "unread",
    )
    if site_id:
        q = q.filter(Notification.site_id == site_id)
    affected = q.update({"status": "read", "read_at": datetime.now(timezone.utc)})
    db.commit()
    return {"updated": affected}


@router.delete("/{notification_id}")
def delete_notification(notification_id: str, db: Session = Depends(get_db), manager: Manager = Depends(require_auth)):
    n = db.query(Notification).filter(
        Notification.manager_id == manager.id,
        Notification.id == notification_id,
    ).first()
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(n)
    db.commit()
    return {"notification_id": notification_id, "deleted": True}