"""
Uncertainty Router Agent — V2
Decides whether the pipeline can auto-proceed, rewrite, compare versions,
escalate to human review, or hard-stop based on scores and risk signals.
"""

import json
from pathlib import Path
from datetime import datetime
from config import get_client, DEFAULT_MODEL

client = get_client()

# Routing thresholds — mirror the V2 spec
THRESHOLDS = {
    "approve_min_weighted_score": 8.0,
    "rewrite_min_weighted_score": 6.5,   # below this → human or rebuild
    "approve_groundedness": 0.85,
    "rewrite_groundedness": 0.70,         # below this → block + escalate
    "min_confidence": 0.65,               # below this → human review
    "max_revisions_before_human": 3,
    "evidence_risk_max": 6.0,             # above this → human review
}

# Actions the router can return
ACTIONS = {
    "AUTO_APPROVE": "auto_approve",
    "AUTO_REWRITE": "auto_rewrite",
    "COMPARE_VERSIONS": "compare_versions",
    "HUMAN_REVIEW": "human_review",
    "HARD_STOP": "hard_stop",
}


def route(
    rubric_score: float | None = None,
    groundedness_score: float | None = None,
    critic_confidence: float | None = None,
    revision_count: int = 0,
    artifact_type: str = "chapter",
    evidence_risk: float = 0.0,
    judges_disagree: bool = False,
    prior_version_exists: bool = False,
    has_legal_medical_financial: bool = False,
) -> dict:
    """
    Route the pipeline to the next action.

    Returns dict with: action, reason, priority, escalation_note
    """
    reasons = []
    action = ACTIONS["AUTO_APPROVE"]
    priority = "normal"

    # Hard stops first
    if has_legal_medical_financial:
        reasons.append("Chapter contains legal/medical/financial claims presented as fact")
        action = ACTIONS["HUMAN_REVIEW"]
        priority = "critical"

    # Groundedness blocks
    if groundedness_score is not None:
        if groundedness_score < THRESHOLDS["rewrite_groundedness"]:
            reasons.append(f"Groundedness score {groundedness_score:.0%} below block threshold (70%)")
            action = ACTIONS["HUMAN_REVIEW"]
            priority = "high"
        elif groundedness_score < THRESHOLDS["approve_groundedness"]:
            reasons.append(f"Groundedness score {groundedness_score:.0%} — rewrite flagged claims only")
            action = ACTIONS["AUTO_REWRITE"]

    # Rubric score routing
    if rubric_score is not None:
        if rubric_score >= THRESHOLDS["approve_min_weighted_score"]:
            if action == ACTIONS["AUTO_APPROVE"]:
                reasons.append(f"Rubric score {rubric_score:.1f} — above approval threshold")
        elif rubric_score >= THRESHOLDS["rewrite_min_weighted_score"]:
            reasons.append(f"Rubric score {rubric_score:.1f} — rewrite required")
            if action in (ACTIONS["AUTO_APPROVE"],):
                action = ACTIONS["AUTO_REWRITE"]
        else:
            reasons.append(f"Rubric score {rubric_score:.1f} — below minimum, rebuild or human review")
            action = ACTIONS["HUMAN_REVIEW"]
            priority = "high"

    # Confidence routing
    if critic_confidence is not None and critic_confidence < THRESHOLDS["min_confidence"]:
        reasons.append(f"Critic confidence {critic_confidence:.0%} below threshold (65%)")
        if action not in (ACTIONS["HUMAN_REVIEW"], ACTIONS["HARD_STOP"]):
            action = ACTIONS["HUMAN_REVIEW"]
        priority = "high"

    # Revision count
    if revision_count >= THRESHOLDS["max_revisions_before_human"]:
        reasons.append(f"Artifact has been revised {revision_count} times — escalating to human")
        action = ACTIONS["HUMAN_REVIEW"]
        priority = "high"

    # Evidence risk
    if evidence_risk > THRESHOLDS["evidence_risk_max"]:
        reasons.append(f"Evidence risk score {evidence_risk:.1f} exceeds threshold")
        action = ACTIONS["HUMAN_REVIEW"]
        priority = "high"

    # Judge disagreement
    if judges_disagree:
        reasons.append("Two judges disagree materially — pairwise comparison recommended")
        if prior_version_exists and action == ACTIONS["AUTO_REWRITE"]:
            action = ACTIONS["COMPARE_VERSIONS"]

    # If prior version exists and rewriting, prefer comparison
    if prior_version_exists and action == ACTIONS["AUTO_REWRITE"]:
        action = ACTIONS["COMPARE_VERSIONS"]
        reasons.append("Prior version exists — will compare versions after rewrite")

    result = {
        "action": action,
        "reasons": reasons,
        "priority": priority,
        "escalation_note": (
            "This artifact requires human judgment before the pipeline can continue."
            if action == ACTIONS["HUMAN_REVIEW"]
            else ""
        ),
        "inputs_received": {
            "rubric_score": rubric_score,
            "groundedness_score": groundedness_score,
            "critic_confidence": critic_confidence,
            "revision_count": revision_count,
            "artifact_type": artifact_type,
            "evidence_risk": evidence_risk,
            "judges_disagree": judges_disagree,
        },
    }

    # If human review, add to queue
    if action == ACTIONS["HUMAN_REVIEW"]:
        _queue_for_human_review(artifact_type, result, priority)

    print(f"\n🔀 Uncertainty Router — {artifact_type}")
    print(f"   Action   : {action.upper()}")
    print(f"   Priority : {priority.upper()}")
    for r in reasons:
        print(f"   • {r}")

    return result


def _queue_for_human_review(artifact_type: str, route_result: dict, priority: str):
    """Append item to the human review queue."""
    queue_path = Path(__file__).parent / "memory" / "human_review_queue.json"
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(queue_path) as f:
            queue = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        queue = {"pending_items": []}

    queue["pending_items"].append({
        "artifact_type": artifact_type,
        "queued_at": datetime.utcnow().isoformat(),
        "priority": priority,
        "reasons": route_result["reasons"],
        "inputs": route_result["inputs_received"],
        "status": "pending",
    })

    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)

    print(f"   → Added to human review queue ({queue_path.name})")


if __name__ == "__main__":
    # Test scenarios
    print("=== Scenario 1: High quality chapter, auto-approve ===")
    print(route(rubric_score=8.5, groundedness_score=0.91, critic_confidence=0.85, revision_count=1, artifact_type="chapter"))

    print("\n=== Scenario 2: Low groundedness, escalate ===")
    print(route(rubric_score=7.2, groundedness_score=0.62, critic_confidence=0.70, revision_count=2, artifact_type="chapter"))

    print("\n=== Scenario 3: Too many revisions ===")
    print(route(rubric_score=7.5, groundedness_score=0.80, critic_confidence=0.72, revision_count=4, artifact_type="chapter"))
