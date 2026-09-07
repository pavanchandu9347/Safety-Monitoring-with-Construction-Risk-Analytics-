import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from app.database.database import Base


def gen_uuid():
    return str(uuid.uuid4())


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
