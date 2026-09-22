"""Evidence-based risk-alert notifications (Milestone 4).

Every notification is derived from REAL analysis output — the risk/safety
scores, persisted violations, hazards, safety alerts and insurance incidents
produced by the video pipeline. No field is fabricated: if a contributing cause
cannot be tied to real data the notification says so explicitly
(``Evidence unavailable ...``) instead of inventing one.

Policy (all configurable via environment, defaults reflect the project's
HIGH=50 / CRITICAL=75 scoring bands):

  * CRITICAL risk/safety level, a CRITICAL alert/violation/incident
            -> immediate notification (severity CRITICAL), in-app + email.
  * HIGH score above ``RISK_ALERT_THRESHOLD`` / ``SAFETY_ALERT_THRESHOLD``
            or a HIGH alert/violation -> severity HIGH, in-app + email.
  * MEDIUM conditions (no HIGH+)           -> in-app only, no external channel.
  * LOW conditions                         -> no notification.

Repeated notifications for the same continuous condition ("dust level high")
are suppressed by ``NOTIFICATION_COOLDOWN_SECONDS``. A severity escalation
(e.g. HIGH -> CRITICAL) BYPASSES the cooldown so an immediate escalation alert
is always delivered.

NOT SETUP / FAILURE SAFETY: external email is attempted only when SMTP settings
and the manager's address are configured. Any failure in the email path is
caught and logged — it NEVER fails or alters the analysis it was called from.
"""

from __future__ import annotations

import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import (
    EMAIL_ALERT_MIN_LEVEL,
    NOTIFICATION_COOLDOWN_SECONDS,
    NOTIFICATION_EMAIL_FROM,
    RISK_ALERT_THRESHOLD,
    SAFETY_ALERT_THRESHOLD,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)
from app.live.hub import NOTIFICATION_HUB
from app.models.models import Manager, Notification, Site, VideoAnalysis

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
_EXTERNAL_LEVEL_RANK = _SEVERITY_RANK.get(EMAIL_ALERT_MIN_LEVEL or "HIGH", 2)

NOTIFICATION_WIDTH = "in-app"
NOTIFICATION_CHANNEL_EXTERNAL = "email"


class _Condition:
    """A single, real, explainable reason to raise an alert."""

    __slots__ = ("tag", "type", "severity", "title", "message", "risk_score", "evidence", "recommendations")

    def __init__(
        self,
        tag: str,
        type_: str,
        severity: str,
        title: str,
        message: str,
        risk_score: Optional[float] = None,
        evidence: Optional[dict] = None,
        recommendations: Optional[list] = None,
    ):
        self.tag = tag
        self.type = type_
        self.severity = severity
        self.title = title
        self.message = message
        self.risk_score = risk_score
        self.evidence = evidence or {}
        self.recommendations = recommendations or []


def _now() -> datetime:
    # Naive UTC to match the model's default (``datetime.utcnow``) and every
    # persisted value. Mixing a tz-aware cutoff into a naive timestamp column
    # breaks cooldown comparisons under PostgreSQL (server TZ conversion).
    return datetime.utcnow()


def _rank(severity: str) -> int:
    return _SEVERITY_RANK.get(str(severity).upper(), 0)


def _label(sev: int) -> str:
    for name, rank in sorted(_SEVERITY_RANK.items(), key=lambda kv: kv[1], reverse=True):
        if sev >= rank:
            return name
    return "LOW"


def _score_severity(level: str, score: float) -> int:
    """Severity rank derived from the real analysis level, cross-checked by score."""
    sev = _rank(level)
    if score >= 75:
        sev = max(sev, _rank("CRITICAL"))
    elif score >= 50:
        sev = max(sev, _rank("HIGH"))
    return sev


def evaluate_analysis(
    db: Session,
    site_id: str,
    analysis_id: str,
    *,
    risk=None,
    safety=None,
    alerts=None,
    violations=None,
    hazards=None,
    incidents=None,
) -> list[Notification]:
    """Decide which evidence-based notifications to raise for an analysis run.

    Accepts the persisted, real results of the analysis (summaries + rows).
    Returns the list of newly created ``Notification`` rows.
    """
    risk = risk if isinstance(risk, dict) else {}
    safety = safety if isinstance(safety, dict) else {}
    alerts = alerts or []
    violations = violations or []
    hazards = hazards or []
    incidents = incidents or []

    risk_score = float(risk.get("overall_score", 0) or 0)
    safety_score = float(safety.get("overall_safety_score", 0) or 0)
    risk_level = str(risk.get("risk_level", "LOW")).upper()
    safety_level = str(safety.get("overall_safety_level", "LOW")).upper()

    factors = _collect_factors(risk)
    ppe = safety.get("ppe_compliance", {})
    workers_affected = sorted({v.get("worker_id") for v in violations if v.get("worker_id")})
    zones = sorted({h.get("zone_id") for h in hazards if h.get("zone_id")} | {a.get("zone_id") for a in alerts if a.get("zone_id")})

    base_evidence = {
        "analysis_id": analysis_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "overall_safety_score": safety_score,
        "overall_safety_level": safety_level,
        "contributing_factors": factors,
        "violations": [
            {"worker_id": v.get("worker_id"), "type": v.get("violation_type"), "severity": v.get("severity")}
            for v in violations
        ],
        "hazards": [
            {"description": h.get("hazard_type") or h.get("description"), "severity": h.get("severity"), "zone_id": h.get("zone_id")}
            for h in hazards
        ],
        "alerts": [
            {"message": a.get("message"), "severity": a.get("severity"), "zone_id": a.get("zone_id")}
            for a in alerts
        ],
        "incidents": [
            {"description": i.get("description"), "severity": i.get("severity")}
            for i in incidents
        ],
        "ppe_compliance": {
            "score": ppe.get("score") if isinstance(ppe, dict) else None,
            "compliant": ppe.get("compliant_count") if isinstance(ppe, dict) else None,
            "non_compliant": ppe.get("non_compliant_count") if isinstance(ppe, dict) else None,
            "insufficient_evidence": ppe.get("insufficient_evidence_count") if isinstance(ppe, dict) else None,
        },
        "workers_affected": workers_affected,
        "zone_ids": zones,
        "evidence_note": (
            "Contributing factors derived from video, sensor and inspection data."
            if factors
            else "Evidence unavailable for specific contributing causes."
        ),
    }

    conditions: list[_Condition] = [_risk_condition(risk, risk_score, risk_level, base_evidence)]

    safety_conditions = _safety_conditions(safety, safety_score, safety_level, base_evidence)
    conditions.extend(safety_conditions)

    conditions.extend(_row_conditions(alerts, violations, hazards, incidents, base_evidence))

    def _condition_priority(c: _Condition) -> tuple:
        # Highest severity wins; the generic risk/safety summaries are the
        # weakest tie-breaker so a specific, actionable condition (e.g. a PPE
        # evidence gap or a concrete hazard) surfaces when severity ties.
        specific = 0 if c.tag in ("risk", "safety") else 1
        return (_rank(c.severity), c.risk_score if c.risk_score is not None else 0, specific)

    # Keep only the strongest condition; it explains the alert and determines
    # severity, while evidence below still shows every contributing factor.
    strongest = max(conditions, key=_condition_priority) if conditions else None
    if strongest is None or _rank(strongest.severity) < _rank("MEDIUM"):
        return []

    created: list[Notification] = []

    # One notification per manager authorized for the site (evidence-tracked).
    managers = (
        db.query(Manager)
        .filter(Manager.site_id == site_id, Manager.is_active == 1)
        .all()
    )
    if managers:
        site = db.query(Site).filter(Site.id == site_id).first()
        # PostgreSQL enforces the notification -> analysis foreign key. Real
        # pipeline runs always persist the analysis first; for defensive callers
        # who pass an id that does not exist we still keep the reference inside
        # ``evidence`` but store a NULL link so referential integrity holds.
        analysis_exists = db.query(VideoAnalysis.id).filter(VideoAnalysis.id == analysis_id).first() is not None
        link_analysis_id = analysis_id if analysis_exists else None
        for manager in managers:
            decision = _decide(
                db,
                site_id=site_id,
                condition=strongest,
                recommendations=strongest.recommendations or _collect_recommendations(risk, safety),
            )
            if decision is None:
                continue
            notification = Notification(
                manager_id=manager.id,
                site_id=site_id,
                analysis_id=link_analysis_id,
                type=strongest.type,
                severity=decision["severity"],
                title=strongest.title,
                message=strongest.message,
                source="analysis_pipeline",
                risk_score=strongest.risk_score,
                evidence=strongest.evidence or base_evidence,
                dedup_key=decision["dedup_key"],
            )
            db.add(notification)
            created.append(notification)

    if created:
        db.commit()
        for n in created:
            db.refresh(n)
            _deliver(n, site=site if managers else None)
    return created


# ── Condition builders ─────────────────────────────────────────────────────────

def _risk_condition(risk, risk_score, risk_level, evidence) -> _Condition:
    # Severity comes from the REAL analysis level/score. When the score is
    # below the configured alert threshold an otherwise-HIGH alert is downgraded
    # to MEDIUM (delivered in-app only) rather than being skipped or promoted.
    sev = _score_severity(risk_level, risk_score)
    if sev >= _rank("HIGH") and risk_score < RISK_ALERT_THRESHOLD:
        sev = _rank("MEDIUM")
    severity = _label(sev)
    return _Condition(
        tag="risk",
        type_="risk_alert",
        severity=severity,
        title="Risk alert",
        message=(
            f"{evidence['evidence_note']} Overall risk score {risk_score:.0f}/100 "
            f"({risk_level})."
        ),
        risk_score=risk_score,
        evidence=evidence,
        recommendations=risk.get("recommendations") or [],
    )


def _safety_conditions(safety, safety_score, safety_level, evidence) -> list[_Condition]:
    conds: list[_Condition] = []
    ppe = safety.get("ppe_compliance") if isinstance(safety, dict) else {}
    insufficient = (ppe or {}).get("insufficient_evidence_count", 0) if isinstance(ppe, dict) else 0
    ppe_score = (ppe or {}).get("score") if isinstance(ppe, dict) else None

    sev = _score_severity(safety_level, safety_score)
    if sev >= _rank("HIGH") and safety_score < SAFETY_ALERT_THRESHOLD:
        sev = _rank("MEDIUM")
    severity = _label(sev)
    if sev >= _rank("MEDIUM"):
        conds.append(_Condition(
            tag="safety",
            type_="safety_alert",
            severity=severity,
            title=f"Site safety score {severity}",
            message=(
                f"{evidence['evidence_note']} Overall safety score {safety_score:.0f}/100 "
                f"({safety_level})."
            ),
            risk_score=safety_score,
            evidence=evidence,
            recommendations=(safety or {}).get("recommendations") or [],
        ))

    if insufficient and insufficient > 0:
        conds.append(_Condition(
            tag="ppe:insufficient_evidence",
            type_="ppe_alert",
            severity="MEDIUM",
            title="PPE check could not be fully verified",
            message=(
                f"{insufficient} worker(s) had insufficient visual evidence to determine "
                "PPE compliance. The assessment was not guessed — revise video angles "
                "so each worker is fully visible."
            ),
            risk_score=ppe_score if ppe_score is not None else None,
            evidence=evidence,
        ))
    return conds


def _row_conditions(alerts, violations, hazards, incidents, evidence) -> list[_Condition]:
    conds: list[_Condition] = []
    for a in alerts:
        sev = str(a.get("severity", "")).upper()
        if sev not in ("HIGH", "CRITICAL"):
            continue
        conds.append(_Condition(
            tag=f"alert:{a.get('id') or a.get('message')}",
            type_="safety_alert",
            severity=sev,
            title=f"Safety alert: {a.get('message') or 'condition detected'}",
            message=f"{a.get('message')} (zone: {a.get('zone_id') or 'unknown'}).",
            evidence=evidence,
        ))
    for v in violations:
        sev = str(v.get("severity", "")).upper()
        if sev not in ("HIGH", "CRITICAL"):
            continue
        conds.append(_Condition(
            tag=f"violation:{v.get('id') or v.get('violation_type')}",
            type_="ppe_alert",
            severity=sev,
            title=f"PPE violation: {v.get('violation_type')}",
            message=(
                f"{v.get('description') or v.get('violation_type')} "
                f"(worker: {v.get('worker_id') or 'unknown'})."
            ),
            evidence=evidence,
        ))
    for h in hazards:
        sev = str(h.get("severity", "")).upper()
        if sev not in ("HIGH", "CRITICAL"):
            continue
        desc = h.get("description") or h.get("hazard_type") or h.get("category") or "hazard"
        conds.append(_Condition(
            tag=f"hazard:{h.get('id') or desc}",
            type_="risk_alert",
            severity=sev,
            title=f"Hazard: {desc}",
            message=f"{desc} in zone {h.get('zone_id') or 'unknown'}.",
            evidence=evidence,
        ))
    for i in incidents:
        sev = str(i.get("severity", "")).upper()
        if sev not in ("HIGH", "CRITICAL"):
            continue
        conds.append(_Condition(
            tag=f"incident:{i.get('id') or i.get('description')}",
            type_="incident",
            severity=sev,
            title=f"Incident: {i.get('description')}",
            message=i.get("description", "Incident recorded."),
            evidence=evidence,
        ))
    return conds


def _collect_factors(risk) -> list[dict]:
    out: list[dict] = []
    for key in ("environmental_factors", "equipment_factors", "site_condition_factors", "activity_factors"):
        for item in risk.get(key, []) if isinstance(risk, dict) else []:
            if isinstance(item, dict):
                out.append({
                    "factor": item.get("factor") or item.get("description") or item.get("category"),
                    "severity": item.get("severity") or item.get("level"),
                    "basis": "video/inspection data",
                    "evidence": item.get("evidence") or item.get("basis"),
                })
            elif isinstance(item, str):
                out.append({"factor": item, "severity": None, "basis": "video/inspection data", "evidence": None})
    return out


def _collect_recommendations(risk, safety) -> list[Any]:
    out: list[Any] = []
    out.extend((risk or {}).get("recommendations", []) or [])
    out.extend((safety or {}).get("recommendations", []) or [])
    # De-duplicate while preserving order.
    seen = set()
    unique = []
    for r in out:
        key = r if isinstance(r, str) else (r.get("recommendation") if isinstance(r, dict) else repr(r))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ── Deduplication / cooldown / escalation ─────────────────────────────────────
def _decide(db: Session, *, site_id: str, condition: _Condition, recommendations: list) -> Optional[dict]:
    """Return a delivery decision dict or ``None`` when the alert is suppressed."""
    tag = condition.tag
    dedup_key = f"{site_id}:{tag}"
    new_sev = _rank(condition.severity)

    # Conditions below MEDIUM never notify.
    if new_sev < _rank("MEDIUM"):
        return None

    recent = (
        db.query(Notification)
        .filter(
            Notification.site_id == site_id,
            Notification.dedup_key == dedup_key,
            Notification.created_at >= _now() - timedelta(seconds=NOTIFICATION_COOLDOWN_SECONDS),
        )
        .all()
    )

    suppress = False
    escalation = False
    if recent:
        highest_stored = max((_rank(n.severity) for n in recent), default=0)
        if new_sev <= highest_stored:
            # Same or weaker condition within cooldown -> suppressed (continuous
            # condition, not worth re-spamming the manager).
            suppress = True
        else:
            # Escalation (e.g. HIGH -> CRITICAL) always delivers immediately.
            escalation = True

    if suppress:
        logger.info(
            "notification suppressed (cooldown %ss): site=%s key=%s sev=%s",
            NOTIFICATION_COOLDOWN_SECONDS, site_id, dedup_key, condition.severity,
        )
        return None

    severity = condition.severity
    if escalation:
        severity = "CRITICAL"
        dedup_key = f"{site_id}:{tag}:escalation"

    if recommendations:
        message = f"{condition.message} Next steps: {'; '.join(map(str, recommendations[:3]))}"
        condition.message = message

    return {"severity": severity, "dedup_key": dedup_key, "escalation": escalation}


# ── Delivery: WS push + optional SMTP email ───────────────────────────────────
def _deliver(n: Notification, site: Optional[Site] = None) -> None:
    payload = {
        "type": "notification",
        "data": {
            "id": n.id,
            "site_id": n.site_id,
            "analysis_id": n.analysis_id,
            "type": n.type,
            "severity": n.severity,
            "title": n.title,
            "message": n.message,
            "source": n.source,
            "risk_score": n.risk_score,
            "status": n.status,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "evidence_available": bool(n.evidence and n.evidence.get("contributing_factors")),
        },
    }
    try:
        NOTIFICATION_HUB.broadcast(n.site_id, payload)
    except Exception:  # noqa: BLE001
        logger.exception("notification broadcast failed for %s", n.id)

    manager_email = n.manager.email if n.manager else None
    if _rank(n.severity) >= _EXTERNAL_LEVEL_RANK and manager_email:
        _send_email(n, manager_email, site.name if site else None)


def _send_email(n: Notification, to: str, site_name: Optional[str]) -> None:
    """Send the external email alert. Every failure is logged, never raised."""
    if not (SMTP_HOST and NOTIFICATION_EMAIL_FROM):
        logger.info(
            "external email not configured (SMTP_HOST/NOTIFICATION_EMAIL_FROM empty); "
            "in-app notification %s (%s) is still active for %s",
            n.id, n.severity, to,
        )
        return
    subject = f"[BuildSure] {n.severity} alert: {n.title} ({n.site_id})"
    site_line = f"\nSite: {site_name or n.site_id}\n" if site_name else f"\nSite: {n.site_id}\n"
    body = (
        f"{n.title}\n"
        f"Severity: {n.severity}\n{site_line}"
        f"{n.message}\n"
    )
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = NOTIFICATION_EMAIL_FROM
    msg["To"] = to
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USERNAME:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(NOTIFICATION_EMAIL_FROM, [to], msg.as_string())
        logger.info("notification email sent to %s (%s)", to, n.id)
    except Exception:  # noqa: BLE001
        logger.exception("notification email to %s failed; in-app notification remains", to)