"""Insurance Agent — Milestone 3.

Assesses insurance exposure, classifies incident severity, analyzes claim risk,
and produces an explainable insurance risk score. Every number derives from the
real safety/hazard/incident evidence produced by the shared video pipeline —
no fabricated incidents or scores.
"""

from app.agents.insurance_agent.agent import InsuranceAgent

__all__ = ["InsuranceAgent"]