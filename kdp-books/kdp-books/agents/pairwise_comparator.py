"""
Pairwise Comparator Agent — V2
Compares two versions of the same artifact and selects the better one
using a structured rubric. More reliable than absolute single-version scoring.
"""

import json
from pathlib import Path
from datetime import datetime
from config import get_client, DEFAULT_MODEL

client = get_client()


def compare_versions(
    version_a: str,
    version_b: str,
    artifact_type: str,
    artifact_id: str,
    context: str = "",
    rubric: dict | None = None,
) -> dict:
    """
    Compare two artifact versions and select the better one.

    Args:
        version_a: Full text of Version A (usually the existing approved version).
        version_b: Full text of Version B (the new rewrite).
        artifact_type: chapter, outline, brief, opening, subtitle, back_cover
        artifact_id: Used for saving the comparison report.
        context: Voice bible, market context, prior chapters, etc.
        rubric: Optional evaluation rubric; if None uses default criteria.

    Returns:
        dict with winner, margin, reasons, retained_version, recommendation
    """
    rubric_text = json.dumps(rubric, indent=2) if rubric else "Use these default criteria: clarity, novelty, reader_value, tone_consistency, argument_strength, practical_payoff"

    system_prompt = """You are the Pairwise Comparator. You compare two versions of the same
content artifact and select which is genuinely better. You are not looking for the safer choice —
you are looking for the one that serves the reader and the book's commercial goals better.
Do not hedge. Make a clear decision. Output valid JSON only."""

    user_prompt = f"""Compare these two versions of a {artifact_type} and determine which is better.

ARTIFACT TYPE: {artifact_type}
CONTEXT: {context or "None provided."}

EVALUATION RUBRIC / CRITERIA:
{rubric_text}

VERSION A:
---
{version_a}
---

VERSION B:
---
{version_b}
---

For each criterion, score both versions from 1–10 and note which wins.
Then make a final decision.

IMPORTANT RULE: If the versions are very close (margin < 0.5), retain Version A to avoid
unnecessary churn. Only replace Version A if Version B clearly wins on at least 3 criteria.

Return this exact JSON:
{{
  "criterion_scores": {{
    "<criterion>": {{
      "version_a_score": <float>,
      "version_b_score": <float>,
      "winner": "A" | "B" | "tie"
    }}
  }},
  "version_a_total": <float>,
  "version_b_total": <float>,
  "margin": <float>,
  "winner": "A" | "B",
  "criteria_won_by_b": <int>,
  "retain_version_a": <bool>,
  "retained_version": "A" | "B",
  "reasons": ["<reason 1>", "<reason 2>", ...],
  "recommendation": "<one sentence action>"
}}"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    # Enforce anti-churn rule
    if result.get("margin", 1.0) < 0.5 or result.get("criteria_won_by_b", 0) < 3:
        result["retain_version_a"] = True
        result["retained_version"] = "A"
        result["recommendation"] = "Margin too small — retaining Version A to avoid churn."

    # Save comparison report
    output_dir = Path(__file__).parent / "memory" / "version_comparisons"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"compare_{artifact_type}_{artifact_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report = {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "compared_at": datetime.utcnow().isoformat(),
        **result,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n⚖️  Pairwise Comparator — {artifact_type} [{artifact_id}]")
    print(f"   Version A Score  : {result.get('version_a_total', '?'):.1f}")
    print(f"   Version B Score  : {result.get('version_b_total', '?'):.1f}")
    print(f"   Margin           : {result.get('margin', 0):.1f}")
    print(f"   Winner           : Version {result.get('winner', '?')}")
    print(f"   Retained         : Version {result.get('retained_version', '?')}")
    print(f"   → {result.get('recommendation', '')}")

    return report


if __name__ == "__main__":
    a = "Opening A: Most men fail with women because they try too hard to impress."
    b = "Opening B: The moment a man starts performing for a woman, she stops seeing him clearly — and so does he."
    result = compare_versions(a, b, "opening", "chapter_01_opening")
    print(json.dumps(result, indent=2))
