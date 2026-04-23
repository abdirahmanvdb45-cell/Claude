"""
Grounding Auditor Agent — V2
Checks whether research-sensitive claims are supported by known facts or source material.
Returns a groundedness score, per-claim verdicts, and rewrite instructions.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()


def audit_grounding(
    claims: list[dict],
    chapter_number: int,
    source_facts: list[str] | None = None,
) -> dict:
    """
    Audit a list of extracted claims against available source facts.

    Args:
        claims: List of claim dicts from claim_extractor.extract_claims()
        chapter_number: Chapter number for report naming.
        source_facts: Optional list of known facts / research excerpts to check against.
                      If empty, the auditor assesses plausibility and flags unsupported claims.

    Returns:
        dict with groundedness_score, per-claim verdicts, decision
    """
    facts_text = "\n".join(f"- {f}" for f in source_facts) if source_facts else (
        "No external source facts provided. Audit based on plausibility and claim type only."
    )

    claims_text = json.dumps(claims, indent=2)

    system_prompt = """You are the Grounding Auditor. You verify whether claims in nonfiction
writing are actually supported by the provided facts. You do not guess or assume support exists.
If support is weak, you mark it weak. If no evidence exists, you recommend reframing or removal.
Output valid JSON only — no prose, no markdown fences."""

    user_prompt = f"""Audit the following claims for grounding and evidence support.

CHAPTER NUMBER: {chapter_number}

AVAILABLE FACTS / SOURCE MATERIAL:
{facts_text}

CLAIMS TO AUDIT:
{claims_text}

For each claim, determine its status:
- "fully_supported": strong evidence exists in the provided facts
- "partially_supported": some evidence, but claim goes slightly beyond it
- "unsupported": no evidence found; claim may be plausible but unverified
- "overextended": claim makes a broader assertion than the evidence supports
- "opinion_acceptable": clearly framed opinion; no verification needed

For unsupported or overextended claims, provide a rewrite instruction.

Return this JSON structure:
{{
  "chapter_number": {chapter_number},
  "total_claims_audited": <int>,
  "groundedness_score": <float 0.0-1.0>,
  "supported_claims": ["<claim_id>", ...],
  "partially_supported_claims": ["<claim_id>", ...],
  "unsupported_claims": ["<claim_id>", ...],
  "overextended_claims": ["<claim_id>", ...],
  "claim_verdicts": {{
    "<claim_id>": {{
      "status": "<status>",
      "verdict_note": "<brief explanation>",
      "rewrite_instruction": "<optional rewrite guidance>"
    }}
  }},
  "decision": "<approve|rewrite_flagged|block_escalate>",
  "auditor_notes": "<overall assessment>"
}}

Decision rules:
- groundedness_score >= 0.85 → "approve"
- groundedness_score 0.70–0.84 → "rewrite_flagged" (only flagged claims need fixing)
- groundedness_score < 0.70 → "block_escalate" (chapter needs significant rework)"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    # Save grounding report
    output_dir = Path(__file__).parent / "memory" / "grounding"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"grounding_report_chapter_{chapter_number:02d}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n✅ Grounding Auditor — Chapter {chapter_number}")
    print(f"   Groundedness Score : {result.get('groundedness_score', 0):.0%}")
    print(f"   Decision           : {result.get('decision', 'unknown').upper()}")
    print(f"   Unsupported        : {len(result.get('unsupported_claims', []))} claims")
    print(f"   Overextended       : {len(result.get('overextended_claims', []))} claims")
    print(f"   Saved to           : {report_path}")

    return result


def audit_chapter(chapter_text: str, chapter_number: int, source_facts: list[str] | None = None) -> dict:
    """
    Full pipeline: extract claims then audit grounding in one call.
    Convenience method for automation_agent.py.
    """
    from claim_extractor import extract_claims

    claim_result = extract_claims(chapter_text, chapter_number)
    claims = claim_result.get("claims", [])

    if not claims:
        return {
            "chapter_number": chapter_number,
            "groundedness_score": 1.0,
            "decision": "approve",
            "auditor_notes": "No claims requiring verification found.",
        }

    # Only audit high/medium risk claims to save API cost
    risky_claims = [c for c in claims if c.get("risk_level") in ("high", "medium")]
    return audit_grounding(risky_claims, chapter_number, source_facts)


if __name__ == "__main__":
    sample_claims = [
        {
            "claim_id": "C2_001",
            "text": "Women consistently respond more strongly to composure under pressure than to verbal reassurance.",
            "type": "behavioral_science_claim",
            "support_required": True,
            "risk_level": "high",
        },
        {
            "claim_id": "C2_002",
            "text": "Research shows stated preferences differ from real-time attraction choices.",
            "type": "statistical_claim",
            "support_required": True,
            "risk_level": "medium",
        },
    ]
    facts = [
        "Speed-dating studies show low correlation between stated preferences and actual partner choices (Eastwick & Finkel, 2008).",
        "Evolutionary psychology literature notes that behavioral cues like decisiveness signal resource-holding potential.",
    ]
    result = audit_grounding(sample_claims, chapter_number=2, source_facts=facts)
    print(json.dumps(result, indent=2))
