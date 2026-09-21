"""Reporting Agent (Milestone 4 - Reporting Intelligence).

The Reporting Agent consumes the unified intelligence context produced by the
Construction Risk Intelligence Engine (plus optional historical analytics) and
assembles a structured executive report. It performs NO new model/scoring work:
every sentence is derived from persisted analysis rows or explicitly stated as
missing evidence.
"""

from app.agents.reporting_agent.agent import ReportingAgent

__all__ = ["ReportingAgent"]