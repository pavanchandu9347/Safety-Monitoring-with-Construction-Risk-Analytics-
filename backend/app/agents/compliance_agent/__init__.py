"""Compliance Agent — Milestone 3.

Validates the site against the reference regulatory baseline using ONLY real
evidence from the existing video-analysis pipeline (workers, PPE, safety
violations, hazards, alerts, risk & accident zones). Requirements that the
platform cannot verify from its evidence are reported as ``NOT_VERIFIED`` with
an explicit reason — never invented as compliant or non-compliant.
"""

from app.agents.compliance_agent.agent import ComplianceAgent

__all__ = ["ComplianceAgent"]