"""Compliance recommendations derived from real findings.

Every recommendation is generated from an actual NON_COMPLIANT finding /
violation. When nothing is non-compliant the engine returns no fabricated
advice — only an evidence-availability note.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _ppe_recommendations(non_compliant_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    ppe = [f for f in non_compliant_findings if f.get("category") == "PPE"]
    if ppe:
        worker_ids: list = []
        for f in ppe:
            worker_ids += f.get("evidence_meta", {}).get("worker_ids", [])
        unique = list(dict.fromkeys(worker_ids))
        if unique:
            recs.append({
                "title": "Enforce PPE compliance",
                "description": (
                    f"Worker(s) {', '.join(unique)} were detected without required "
                    "PPE. Issue replacement equipment and re-educate before resuming work."
                ),
                "priority": "HIGH",
                "source": "compliance_agent",
                "evidence_ref": [f.get("requirement") for f in ppe],
            })
    return recs


def _worker_safety_recs(non_compliant_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    ws = [f for f in non_compliant_findings if f.get("category") in ("Worker Safety", "Equipment Safety")]
    if ws:
        recs.append({
            "title": "Enforce worker–equipment separation",
            "description": (
                "Unsafe worker-equipment proximity was detected. Restrict personnel "
                "from equipment swing/operating zones and post spotter controls."
            ),
            "priority": "CRITICAL",
            "source": "compliance_agent",
            "evidence_ref": [f.get("requirement") for f in ws],
        })
    return recs


def _inspection_recs(inspection_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if inspection_result.get("overdue", 0) > 0:
        return [{
            "title": "Perform overdue inspections",
            "description": (
                f"{inspection_result['overdue']} required inspection(s) are overdue "
                "and no completion record exists. Schedule and document them."
            ),
            "priority": "HIGH",
            "source": "inspection_tracker",
            "evidence_ref": [i["inspection_type"] for i in inspection_result.get("inspections", [])
                             if i.get("status") == "OVERDUE"],
        }]
    return []


def _site_safety_recs(non_compliant_findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    ss = [f for f in non_compliant_findings if f.get("category") == "Site Safety"]
    if ss:
        recs.append({
            "title": "Mitigate site-safety conditions",
            "description": "Site-safety requirements show a non-compliant condition "
                           "(lighting or accident-prone zones). Apply the referenced "
                           "mitigations before operations continue.",
            "priority": "HIGH",
            "source": "compliance_agent",
            "evidence_ref": [f.get("requirement") for f in ss],
        })
    return recs


def generate(
    findings: List[Dict[str, Any]],
    policy_violations: List[Dict[str, Any]],
    score_result: Dict[str, Any],
    inspection_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    non_compliant = [f for f in findings if f.get("status") == "NON_COMPLIANT"]
    recs: List[Dict[str, Any]] = []
    recs += _ppe_recommendations(non_compliant)
    recs += _worker_safety_recs(non_compliant)
    recs += _site_safety_recs(non_compliant)
    recs += _inspection_recs(inspection_result)

    if not recs:
        recs.append({
            "title": "Maintain verified compliance posture",
            "description": (
                "No non-compliant compliance finding was derived from the available "
                "evidence. Requirements without evidence were reported as NOT_VERIFIED."
            ),
            "priority": "LOW",
            "source": "compliance_agent",
            "evidence_ref": [],
        })
    return recs