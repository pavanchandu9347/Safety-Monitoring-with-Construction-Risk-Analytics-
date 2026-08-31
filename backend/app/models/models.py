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
