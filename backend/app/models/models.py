import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from app.database.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Manager(Base):
    """Authenticated site manager (Milestone 4).

    ``site_id`` scopes the manager to a single authorized construction site;
    the ``admin`` role is the single exception allowed to access any site.
    Password hashes are non-reversible scrypt digests and are never exposed
    through API responses. ``token_version`` powers server-side logout: every
    JWT carries the version it was issued at, and bumping the version
    invalidates all previously issued tokens.
    """

    __tablename__ = "managers"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="manager")          # manager | admin
    site_id = Column(String, ForeignKey("sites.id"), nullable=True, index=True)
    is_active = Column(Integer, default=1)
    token_version = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    site = relationship("Site", back_populates="managers")
    notifications = relationship("Notification", back_populates="manager", cascade="all, delete-orphan")


class Notification(Base):
    """Evidence-based risk alert targeted at a site manager (Milestone 4).

    Notifications are only created from REAL analysis output (risk/safety
    scores, violations, hazards, alerts, incidents). ``evidence`` stores the
    contributory facts that explain WHY the alert was raised; ``dedup_key`` lets
    the service suppress repeated alerts for the same continuous condition and
    ``severity`` rank enables immediate escalation notifications.
    """

    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=gen_uuid)
    manager_id = Column(String, ForeignKey("managers.id"), nullable=False, index=True)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False, index=True)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    type = Column(String, default="risk_alert")        # risk_alert | safety_alert | ppe_alert | incident
    severity = Column(String, default="MEDIUM")        # MEDIUM | HIGH | CRITICAL
    title = Column(String, nullable=False)
    message = Column(Text, default="")
    source = Column(String, default="analysis_pipeline")
    risk_score = Column(Float, nullable=True)
    evidence = Column(JSON, default=dict)
    dedup_key = Column(String, default="", index=True)
    status = Column(String, default="unread")          # unread | read | resolved
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    read_at = Column(DateTime, nullable=True)

    manager = relationship("Manager", back_populates="notifications")
    site = relationship("Site", back_populates="notifications")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    location = Column(String, default="")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    sites = relationship("Site", back_populates="project", cascade="all, delete-orphan")


class Site(Base):
    __tablename__ = "sites"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="sites")
    zones = relationship("Zone", back_populates="site", cascade="all, delete-orphan")
    monitoring_events = relationship("MonitoringEvent", back_populates="site", cascade="all, delete-orphan")
    hazards = relationship("Hazard", back_populates="site", cascade="all, delete-orphan")
    risk_assessments = relationship("RiskAssessment", back_populates="site", cascade="all, delete-orphan")
    equipment = relationship("Equipment", back_populates="site", cascade="all, delete-orphan")
    workers = relationship("Worker", back_populates="site", cascade="all, delete-orphan")
    safety_violations = relationship("SafetyViolation", back_populates="site", cascade="all, delete-orphan")
    safety_alerts = relationship("SafetyAlert", back_populates="site", cascade="all, delete-orphan")
    safety_assessments = relationship("SafetyAssessment", back_populates="site", cascade="all, delete-orphan")
    compliance_requirements = relationship("ComplianceRequirement", back_populates="site", cascade="all, delete-orphan")
    compliance_findings = relationship("ComplianceFinding", back_populates="site", cascade="all, delete-orphan")
    inspections = relationship("InspectionRecord", back_populates="site", cascade="all, delete-orphan")
    compliance_assessments = relationship("ComplianceAssessment", back_populates="site", cascade="all, delete-orphan")
    insurance_assessments = relationship("InsuranceAssessment", back_populates="site", cascade="all, delete-orphan")
    insurance_incidents = relationship("InsuranceIncident", back_populates="site", cascade="all, delete-orphan")
    claim_records = relationship("ClaimRecord", back_populates="site", cascade="all, delete-orphan")
    managers = relationship("Manager", back_populates="site")
    notifications = relationship("Notification", back_populates="site", cascade="all, delete-orphan")


class VideoAnalysis(Base):
    """A single analysis pass over ONE construction-site video (primary input).

    Every other analysis record (risk, safety, hazards, events, workers,
    equipment, violations, alerts) carries an ``analysis_id`` pointing back to
    this row, so all agents consume the SAME video-derived evidence set.
    """

    __tablename__ = "video_analyses"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    original_filename = Column(String, default="")
    stored_path = Column(String, default="")
    source_type = Column(String, default="stored")  # 'stored' | 'uploaded'
    status = Column(String, default="processing")  # processing | completed | failed
    error = Column(Text, default="")

    duration_seconds = Column(Float, default=0.0)
    fps = Column(Float, default=0.0)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    frame_count = Column(Integer, default=0)

    frame_interval = Column(Integer, default=15)
    max_frames = Column(Integer, default=30)
    frames_analyzed = Column(Integer, default=0)
    model_used = Column(String, default="")

    worker_count = Column(Integer, default=0)
    vehicle_count = Column(Integer, default=0)
    helmet_violations = Column(Integer, default=0)
    vest_violations = Column(Integer, default=0)
    other_violations = Column(Integer, default=0)
    total_violations = Column(Integer, default=0)
    ppe_compliance = Column(Float, default=100.0)
    detected_objects = Column(JSON, default=list)
    ppe_workers = Column(JSON, default=dict)
    evidence = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site")


class Zone(Base):
    __tablename__ = "zones"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    name = Column(String, nullable=False)
    zone_type = Column(String, default="general")
    status = Column(String, default="active")
    risk_level = Column(String, default="LOW")
    current_risk_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site", back_populates="zones")
    monitoring_events = relationship("MonitoringEvent", back_populates="zone")
    hazards = relationship("Hazard", back_populates="zone")


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String, nullable=False)
    source = Column(String, default="system")
    detected_objects = Column(JSON, default=list)
    equipment_activity = Column(JSON, default=dict)
    environmental_conditions = Column(JSON, default=dict)
    site_conditions = Column(JSON, default=dict)
    raw_data = Column(JSON, default=dict)
    description = Column(Text, default="")

    site = relationship("Site", back_populates="monitoring_events")
    zone = relationship("Zone", back_populates="monitoring_events")


class Hazard(Base):
    __tablename__ = "hazards"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    hazard_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, default="LOW")
    risk_contribution = Column(Float, default=0.0)
    evidence = Column(Text, default="")
    source = Column(String, default="system")
    recommended_mitigation = Column(Text, default="")
    status = Column(String, default="detected")
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    site = relationship("Site", back_populates="hazards")
    zone = relationship("Zone", back_populates="hazards")
    risk_assessments = relationship("RiskAssessmentHazard", back_populates="hazard")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    overall_score = Column(Float, default=0.0)
    risk_level = Column(String, default="LOW")
    environmental_score = Column(Float, default=0.0)
    equipment_score = Column(Float, default=0.0)
    site_condition_score = Column(Float, default=0.0)
    activity_score = Column(Float, default=0.0)
    environmental_factors = Column(JSON, default=list)
    equipment_factors = Column(JSON, default=list)
    site_condition_factors = Column(JSON, default=list)
    activity_factors = Column(JSON, default=list)
    summary = Column(Text, default="")

    site = relationship("Site", back_populates="risk_assessments")
    hazards = relationship("RiskAssessmentHazard", back_populates="risk_assessment", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="risk_assessment", cascade="all, delete-orphan")


class RiskAssessmentHazard(Base):
    __tablename__ = "risk_assessment_hazards"

    id = Column(String, primary_key=True, default=gen_uuid)
    risk_assessment_id = Column(String, ForeignKey("risk_assessments.id"), nullable=False)
    hazard_id = Column(String, ForeignKey("hazards.id"), nullable=False)

    risk_assessment = relationship("RiskAssessment", back_populates="hazards")
    hazard = relationship("Hazard", back_populates="risk_assessments")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String, primary_key=True, default=gen_uuid)
    risk_assessment_id = Column(String, ForeignKey("risk_assessments.id"), nullable=False)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String, default="medium")
    hazard_type = Column(String, default="")
    related_hazard_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    risk_assessment = relationship("RiskAssessment", back_populates="recommendations")


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    equipment_type = Column(String, nullable=False)
    status = Column(String, default="idle")
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    activity = Column(String, default="")
    operating_duration_minutes = Column(Integer, default=0)
    maintenance_status = Column(String, default="operational")
    nearby_worker_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site", back_populates="equipment")


class Worker(Base):
    """Worker record for safety monitoring (Milestone 2)."""

    __tablename__ = "workers"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    name = Column(String, default="")
    role = Column(String, default="worker")
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    ppe_status = Column(String, default="compliant")
    missing_ppe = Column(JSON, default=list)
    detected_ppe = Column(JSON, default=list)
    is_present = Column(Integer, default=1)
    last_seen = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site")
    zone = relationship("Zone")


# ── Milestone 3 · Compliance & Insurance Intelligence ────────────────────────


class ComplianceRequirement(Base):
    """A normalized regulatory requirement that a site is measured against.

    Reference data (the requirement/standard), never a result: its ``status``
    field is (re)computed by the Compliance Agent from actual video/document
    evidence at each analysis. ``NOT_VERIFIED`` means the platform has no
    evidence to prove or disprove the requirement.
    """

    __tablename__ = "compliance_requirements"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    category = Column(String, nullable=False)   # PPE | Worker Safety | ...
    requirement = Column(String, nullable=False)
    description = Column(Text, default="")
    severity = Column(String, default="MEDIUM")
    source = Column(String, default="regulatory_standard")
    status = Column(String, default="NOT_VERIFIED")   # COMPLIANT | NON_COMPLIANT | NOT_VERIFIED | NOT_AVAILABLE
    evidence = Column(Text, default="")
    last_checked = Column(DateTime, nullable=True)
    next_review = Column(DateTime, nullable=True)

    site = relationship("Site")
    findings = relationship("ComplianceFinding", back_populates="compliance_requirement")


class ComplianceFinding(Base):
    """A concrete compliance result derived from REAL analysis evidence.

    Each finding references the analysis that produced the underlying safety
    violation/hazard and (optionally) the requirement it maps to.
    """

    __tablename__ = "compliance_findings"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    requirement_id = Column(String, ForeignKey("compliance_requirements.id"), nullable=True)
    category = Column(String, nullable=False)
    requirement = Column(Text, default="")           # snapshot of the requirement text
    description = Column(Text, nullable=False)
    status = Column(String, default="NOT_VERIFIED")   # COMPLIANT | NON_COMPLIANT | NOT_VERIFIED | NOT_AVAILABLE
    severity = Column(String, default="MEDIUM")
    evidence = Column(Text, default="")
    evidence_meta = Column(JSON, default=dict)   # worker ids, frames, timestamps, source ids
    source = Column(String, default="video_vision")
    timestamp = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site")
    compliance_requirement = relationship("ComplianceRequirement", back_populates="findings")


class InspectionRecord(Base):
    """Required inspection for the site.

    ``status`` is NOT_AVAILABLE unless a real inspection record is provided.
    The platform never invents completed inspections.
    """

    __tablename__ = "inspection_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    inspection_type = Column(String, nullable=False)
    description = Column(Text, default="")
    due_date = Column(DateTime, nullable=True)
    last_inspection = Column(DateTime, nullable=True)
    status = Column(String, default="NOT_AVAILABLE")   # COMPLETED | DUE | OVERDUE | NOT_AVAILABLE
    evidence = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site")


class ComplianceAssessment(Base):
    """A stored compliance assessment result for one analysis."""

    __tablename__ = "compliance_assessments"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    overall_score = Column(Float, nullable=True)     # None => insufficient evidence
    compliance_level = Column(String, default="INSUFFICIENT_EVIDENCE")
    category_scores = Column(JSON, default=dict)
    requirements_checked = Column(Integer, default=0)
    compliant_count = Column(Integer, default=0)
    non_compliant_count = Column(Integer, default=0)
    not_verified_count = Column(Integer, default=0)
    open_violations = Column(Integer, default=0)
    overdue_inspections = Column(Integer, default=0)
    evidence_available = Column(Integer, default=0)
    score_basis = Column(Text, default="")
    summary = Column(Text, default="")
    recommendations = Column(JSON, default=list)
    report = Column(JSON, default=dict)

    site = relationship("Site")


class InsuranceAssessment(Base):
    """Stored insurance risk assessment for one analysis."""

    __tablename__ = "insurance_assessments"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String, default="LOW")
    exposure = Column(JSON, default=dict)
    claim_risk = Column(JSON, default=dict)
    open_incidents = Column(Integer, default=0)
    incident_severity = Column(String, default="LOW")
    factors = Column(JSON, default=list)
    evidence = Column(JSON, default=list)
    summary = Column(Text, default="")
    recommendations = Column(JSON, default=list)

    site = relationship("Site")


class InsuranceIncident(Base):
    """A verified incident derived from real high-severity analysis evidence.

    Incidents are only created when the platform actually detected evidence
    (a HIGH/CRITICAL hazard or critical safety alert), never invented.
    """

    __tablename__ = "insurance_incidents"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    incident_type = Column(String, nullable=False)
    description = Column(Text, default="")
    severity = Column(String, default="MEDIUM")
    timestamp = Column(DateTime, default=datetime.utcnow)
    workers_involved = Column(JSON, default=list)
    hazards = Column(JSON, default=list)
    violations = Column(JSON, default=list)
    evidence = Column(JSON, default=dict)
    claim_risk = Column(String, default="LOW")

    site = relationship("Site")


class ClaimRecord(Base):
    """Assembled claim documentation for a verified incident."""

    __tablename__ = "claim_records"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    incident_id = Column(String, ForeignKey("insurance_incidents.id"), nullable=True)
    status = Column(String, default="generated")
    claim_summary = Column(Text, default="")
    documentation = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site")


class SafetyViolation(Base):
    """A recorded PPE violation or unsafe behavior (Milestone 2)."""

    __tablename__ = "safety_violations"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    worker_id = Column(String, ForeignKey("workers.id"), nullable=True)
    violation_type = Column(String, nullable=False)
    description = Column(Text, default="")
    severity = Column(String, default="LOW")
    risk_contribution = Column(Float, default=0.0)
    recommended_mitigation = Column(Text, default="")
    status = Column(String, default="open")
    source = Column(String, default="ppe_detection")
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    site = relationship("Site")


class SafetyAlert(Base):
    """Generated safety alert for operators (Milestone 2)."""

    __tablename__ = "safety_alerts"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    zone_id = Column(String, ForeignKey("zones.id"), nullable=True)
    alert_type = Column(String, nullable=False)
    message = Column(Text, default="")
    severity = Column(String, default="LOW")
    is_acknowledged = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    site = relationship("Site")


class SafetyAssessment(Base):
    """A stored safety assessment result (Milestone 2)."""

    __tablename__ = "safety_assessments"

    id = Column(String, primary_key=True, default=gen_uuid)
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    analysis_id = Column(String, ForeignKey("video_analyses.id"), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    overall_safety_score = Column(Float, default=0.0)
    overall_safety_level = Column(String, default="LOW")
    ppe_score = Column(Float, default=0.0)
    ppe_compliance_rate = Column(Float, default=1.0)
    worker_safety_score = Column(Float, default=0.0)
    worker_count = Column(Integer, default=0)
    accident_zone_score = Column(Float, default=0.0)
    ppe_factors = Column(JSON, default=list)
    worker_factors = Column(JSON, default=list)
    accident_factors = Column(JSON, default=list)
    violation_count = Column(Integer, default=0)
    alert_count = Column(Integer, default=0)
    summary = Column(Text, default="")

    site = relationship("Site")
