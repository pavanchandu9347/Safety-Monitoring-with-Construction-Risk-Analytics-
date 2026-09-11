"""What the platform can legitimately monitor from video vs. documentation.

Video evidence can support *observable* conditions (PPE worn, worker-equipment
proximity, visible hazards, lighting). It cannot prove licenses, training
records, inspection certificates or contractual documentation. This module
classifies each requirement's evidence availability so the validator never
pretends that visual detection proves documentation compliance.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Categories whose requirements are verifiable from construction-site video.
VIDEO_VERIFIABLE: Dict[str, str] = {
    "PPE": "PEERSONAL protective equipment usage observed in frames",
    "Worker Safety": "Worker behavior and worker–equipment proximity observed in frames",
    "Equipment Safety": "Equipment presence and operating zones observed in frames",
    "Site Safety": "Lighting and spatial accident-risk observed in frames",
}

# Categories that fundamentally require documentation/records, not video.
DOCUMENTATION_ONLY: Dict[str, str] = {
    "Inspection": "Requires statutory inspection records — not verifiable from video",
    "Environmental": "Requires sensor/permit records — not available from video evidence",
    "Emergency Preparedness": "Requires emergency equipment/egress inspection records",
    "Documentation": "Requires licenses, certificates, training and insurance records",
}


def classify_evidence(category: str) -> Dict[str, str]:
    """Return how a category's evidence is (or isn't) obtainable."""
    if category in VIDEO_VERIFIABLE:
        return {"evidence_source": "video_vision", "available": "true",
                "basis": VIDEO_VERIFIABLE[category]}
    if category in DOCUMENTATION_ONLY:
        return {"evidence_source": "documentation_required", "available": "false",
                "basis": DOCUMENTATION_ONLY[category]}
    return {"evidence_source": "unknown", "available": "false",
            "basis": "No evidence source defined for this category."}


def monitored_categories(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Which standards/categories the current analysis can actually monitor.

    Only returns categories with at least one piece of available evidence,
    so the UI can show what is genuinely being monitored.
    """
    has_people = bool(context.get("worker_ppe"))
    has_equipment = bool(context.get("equipment"))
    has_accidents = bool((context.get("accident_zones") or {}).get("available"))
    lighting = (context.get("safety") or {}).get("lighting_condition", "") or ""

    results: List[Dict[str, Any]] = []
    for category, basis in VIDEO_VERIFIABLE.items():
        monitored = False
        if category == "PPE":
            monitored = has_people
        elif category == "Worker Safety":
            monitored = has_people or has_equipment
        elif category == "Equipment Safety":
            monitored = has_equipment
        elif category == "Site Safety":
            monitored = bool(lighting) or has_accidents
        results.append({
            "category": category,
            "monitored": monitored,
            "basis": basis,
            "available_evidence": monitored,
        })
    return results