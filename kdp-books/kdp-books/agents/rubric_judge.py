"""
Rubric Judge Agent — V2
Scores every critical artifact against structured rubric criteria.
Returns weighted scores, confidence, decision, and justification in JSON.
"""

import json
import os
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

RUBRICS_DIR = Path(__file__).parent / "memory" / "rubrics"


def load_rubric(artifact_type: str) -> dict:
    rubric_path = RUBRICS_DIR / f"{artifact_type}_rubric.json"
    if not rubric_path.exists():
        raise FileNotFoundError(f"No rubric found for artifact type: {artifact_type}")
    with open(rubric_path, encoding="utf-8") as f:
        return json.load(f)


def judge_artifact(
    artifact_text: str,
    artifact_type: str,
    artifact_context: str = "",
    rubric_override: dict | None = None,
) -> dict:
    """
    Score an artifact against its rubric.

    Args:
        artifact_text: The full text of the artifact to judge.
        artifact_type: One of: brief, outline, chapter, continuity, grounding, commercial
        artifact_context: Additional context (voice bible, prior chapters, market map, etc.)
        rubric_override: Optional rubric dict to use instead of the file-based one.

    Returns:
        dict with keys: criterion_scores, weighted_score, confidence, decision,
                        human_review_recommended, must_fix, uncertainty_notes
    """
    rubric = rubric_override or load_rubric(artifact_type)

    system_prompt = """You are the Rubric Judge. Your only job is to score artifacts against
a structured rubric. You score with precision and honesty. You never inflate scores to be polite.
If the artifact fails a critical dimension, you say so directly.
Output valid JSON only — no prose, no markdown fences."""

    user_prompt = f"""Evaluate the following artifact strictly according to the rubric.

ARTIFACT TYPE: {artifact_type}

CONTEXT:
{artifact_context or "None provided."}

ARTIFACT TEXT:
{artifact_text}

RUBRIC:
{json.dumps(rubric, indent=2)}

INSTRUCTIONS:
1. Score every criterion independently on a 1–10 scale.
2. Multiply each score by its weight and sum for the weighted total.
3. Apply decision thresholds from the rubric exactly.
4. Return a confidence score from 0.0 to 1.0 on how certain you are in your assessment.
5. List any criteria that MUST be fixed before proceeding.
6. Note any areas of genuine uncertainty.

Return this exact JSON structure:
{{
  "criterion_scores": {{
    "<criterion_name>": {{
      "score": <float 1-10>,
      "justification": "<one sentence>"
    }}
  }},
  "weighted_score": <float>,
  "confidence": <float 0-1>,
  "decision": "<approve | rewrite | human_review | rebuild>",
  "human_review_recommended": <bool>,
  "must_fix": ["<issue>", ...],
  "uncertainty_notes": ["<note>", ...]
}}"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if model wraps in them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    # Apply threshold logic from rubric
    thresholds = rubric.get("decision_thresholds", {})
    approve_min = thresholds.get("approve_min_weighted_score", 8.0)
    rewrite_floor = thresholds.get("rewrite_floor", 6.5)

    if result["weighted_score"] >= approve_min and result["decision"] != "human_review":
        result["decision"] = "approve"
    elif result["weighted_score"] < rewrite_floor:
        result["decision"] = "human_review" if result["confidence"] < 0.65 else "rebuild"

    return result


def judge_and_save(
    artifact_text: str,
    artifact_type: str,
    artifact_id: str,
    artifact_context: str = "",
) -> dict:
    """Judge an artifact and persist the report to memory."""
    result = judge_artifact(artifact_text, artifact_type, artifact_context)

    output_dir = Path(__file__).parent / "memory" / "judge_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"judge_{artifact_type}_{artifact_id}.json"

    report = {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        **result,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n📊 Rubric Judge — {artifact_type} [{artifact_id}]")
    print(f"   Weighted Score : {result['weighted_score']:.1f} / 10")
    print(f"   Confidence     : {result['confidence']:.0%}")
    print(f"   Decision       : {result['decision'].upper()}")
    if result["must_fix"]:
        print("   Must Fix:")
        for fix in result["must_fix"]:
            print(f"     • {fix}")

    return report


if __name__ == "__main__":
    # Quick smoke test
    sample = """
    Chapter 2: What She's Actually Testing
    Women continuously evaluate men through everyday interactions — not consciously,
    but instinctively. The signals most men miss are not grand gestures; they are
    small behavioral cues that reveal character under low-stakes conditions.
    """
    report = judge_and_save(sample, "chapter", "chapter_02_test")
    print(json.dumps(report, indent=2))
