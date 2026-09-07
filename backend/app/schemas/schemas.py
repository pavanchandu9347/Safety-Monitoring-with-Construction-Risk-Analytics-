from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HazardStatus(str, Enum):
    detected = "detected"
    investigating = "investigating"
    mitigated = "mitigated"
    resolved = "resolved"


# ── Project ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    location: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    location: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Site ─────────────────────────────────────────────────────────────────────

class SiteCreate(BaseModel):
    project_id: str
    name: str
    description: str = ""


class SiteResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Zone ─────────────────────────────────────────────────────────────────────

class ZoneCreate(BaseModel):
    site_id: str
    name: str
    zone_type: str = "general"


class ZoneResponse(BaseModel):
    id: str
    site_id: str
    name: str
    zone_type: str
    status: str
    risk_level: str
    current_risk_score: float
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Monitoring Event ─────────────────────────────────────────────────────────

class MonitoringEventCreate(BaseModel):
    site_id: str
    zone_id: Optional[str] = None
    event_type: str
    source: str = "system"
    detected_objects: list[dict[str, Any]] = []
    equipment_activity: dict[str, Any] = {}
    environmental_conditions: dict[str, Any] = {}
    site_conditions: dict[str, Any] = {}
    raw_data: dict[str, Any] = {}
    description: str = ""


class MonitoringEventResponse(BaseModel):
    id: str
    site_id: str
    zone_id: Optional[str]
    timestamp: datetime
    event_type: str
    source: str
    detected_objects: list[dict[str, Any]]
    equipment_activity: dict[str, Any]
    environmental_conditions: dict[str, Any]
    site_conditions: dict[str, Any]
    description: str
    model_config = {"from_attributes": True}


# ── Hazard ───────────────────────────────────────────────────────────────────

class HazardResponse(BaseModel):
    id: str
    site_id: str
    zone_id: Optional[str]
    hazard_type: str
    description: str
    severity: str
    risk_contribution: float
    evidence: str
    source: str
    recommended_mitigation: str
    status: str
    timestamp: datetime
    resolved_at: Optional[datetime]
    model_config = {"from_attributes": True}


# ── Risk Assessment ──────────────────────────────────────────────────────────

class RiskFactorDetail(BaseModel):
    factor: str
    contribution: float


class RiskAssessmentResponse(BaseModel):
    id: str
    site_id: str
    timestamp: datetime
    overall_score: float
    risk_level: str
    environmental_score: float
    equipment_score: float
    site_condition_score: float
    activity_score: float
    environmental_factors: list[str]
    equipment_factors: list[str]
    site_condition_factors: list[str]
    activity_factors: list[str]
    summary: str
    model_config = {"from_attributes": True}


# ── Recommendation ───────────────────────────────────────────────────────────

class RecommendationResponse(BaseModel):
    id: str
    risk_assessment_id: str
    site_id: str
    title: str
    description: str
    priority: str
    hazard_type: str
    related_hazard_id: Optional[str]
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Equipment ────────────────────────────────────────────────────────────────

class EquipmentResponse(BaseModel):
    id: str
    site_id: str
    name: str
    equipment_type: str
    status: str
    zone_id: Optional[str]
    activity: str
    operating_duration_minutes: int
    maintenance_status: str
    nearby_worker_count: int
    last_updated: datetime
    model_config = {"from_attributes": True}


# ── Zone Risk Summary ────────────────────────────────────────────────────────

class ZoneRiskSummary(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    risk_score: float
    risk_level: str
    hazard_count: int
    active_hazard_count: int
    event_count: int


# ── Dashboard Response ───────────────────────────────────────────────────────

class RiskTrendPoint(BaseModel):
    timestamp: datetime
    score: float
    risk_level: str


class DashboardResponse(BaseModel):
    site_id: str
    site_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    current_risk_assessment: Optional[RiskAssessmentResponse] = None
    active_hazards: list[HazardResponse] = []
    recent_monitoring_events: list[MonitoringEventResponse] = []
    equipment: list[EquipmentResponse] = []
    zone_risk_data: list[ZoneRiskSummary] = []
    risk_trend: list[RiskTrendPoint] = []
    total_hazards: int = 0
    open_hazards: int = 0
    critical_hazards: int = 0
    total_recommendations: int = 0
    unresolved_recommendations: int = 0
    model_config = {"from_attributes": True}


# ── Video Processing ─────────────────────────────────────────────────────────

class VideoProcessRequest(BaseModel):
    site_id: str
    zone_id: Optional[str] = None
    video_path: str
    frame_interval: int = 30


class ImageAnalyzeRequest(BaseModel):
    site_id: str
    zone_id: Optional[str] = None
    image_path: str


# ── Milestone 2 · Safety Intelligence ─────────────────────────────────────────

class WorkerResponse(BaseModel):
    id: str
    site_id: str
    name: str = ""
    role: str = "worker"
    zone_id: Optional[str] = None
    ppe_status: str = "compliant"
    missing_ppe: list[str] = []
    detected_ppe: list[str] = []
    is_present: int = 1
    last_seen: Optional[datetime] = None
    model_config = {"from_attributes": True}


class SafetyViolationResponse(BaseModel):
    id: str
    site_id: str
    zone_id: Optional[str] = None
    worker_id: Optional[str] = None
    violation_type: str
    description: str = ""
    severity: str = "LOW"
    risk_contribution: float = 0.0
    recommended_mitigation: str = ""
    status: str = "open"
    source: str = "ppe_detection"
    timestamp: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class SafetyAlertResponse(BaseModel):
    id: str
    site_id: str
    zone_id: Optional[str] = None
    alert_type: str
    message: str = ""
    severity: str = "LOW"
    is_acknowledged: int = 0
    timestamp: Optional[datetime] = None
    model_config = {"from_attributes": True}


class SafetyAssessmentResponse(BaseModel):
    id: str
    site_id: str
    timestamp: Optional[datetime] = None
    overall_safety_score: float = 0.0
    overall_safety_level: str = "LOW"
    ppe_score: float = 0.0
    ppe_compliance_rate: float = 1.0
    worker_safety_score: float = 0.0
    worker_count: int = 0
    accident_zone_score: float = 0.0
    ppe_factors: list[str] = []
    worker_factors: list[str] = []
    accident_factors: list[str] = []
    violation_count: int = 0
    alert_count: int = 0
    summary: str = ""
    model_config = {"from_attributes": True}


class SafetyDashboardResponse(BaseModel):
    site_id: str
    site_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    current_safety_assessment: Optional[SafetyAssessmentResponse] = None
    workers: list[WorkerResponse] = []
    violations: list[SafetyViolationResponse] = []
    alerts: list[SafetyAlertResponse] = []
    accident_zone_data: list[dict] = []
    unsafe_behavior_events: list[dict] = []
    total_workers: int = 0
    compliant_workers: int = 0
    violation_count: int = 0
    open_violations: int = 0
    critical_alerts: int = 0
    compliance_rate: float = 1.0
    model_config = {"from_attributes": True}
