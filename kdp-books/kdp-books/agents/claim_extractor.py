"""
Claim Extractor Agent — V2
Scans chapter drafts and extracts factual, empirical, and research-sensitive claims
into machine-checkable JSON so the Grounding Auditor can verify them.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()


def extract_claims(chapter_text: str, chapter_number: int) -> dict:
    """
    Extract all verifiable or high-risk claims from a chapter draft.

    Args:
        chapter_text: Full text of the chapter.
        chapter_number: Chapter number (used for claim IDs and file naming).

    Returns:
        dict with chapter_number, claims list, risk_summary
    """
    system_prompt = """You are the Claim Extractor. You read nonfiction chapters and extract
every factual, empirical, research-sensitive, psychological, or high-risk claim.
Your job is to convert fuzzy prose into a machine-checkable list.
Output valid JSON only — no prose, no markdown fences."""

    user_prompt = f"""Extract all factual or research-sensitive claims from the chapter below.

CHAPTER NUMBER: {chapter_number}

CHAPTER TEXT:
{chapter_text}

CLAIM TYPES to watch for:
- behavioral_science_claim: "men do X", "women respond to Y"
- psychological_claim: references to emotions, cognition, instinct
- statistical_claim: any number, percentage, frequency
- universal_claim: "always", "never", "all", "every"
- causal_claim: "X causes Y", "because of X, Y happens"
- cultural_claim: references to gender norms, society, culture
- opinion_presented_as_fact: subjective assertion stated without qualification

For each claim return:
{{
  "claim_id": "C{chapter_number}_XXX",
  "text": "<exact or near-exact wording from chapter>",
  "type": "<claim type>",
  "support_required": <true|false>,
  "risk_level": "<low|medium|high>",
  "source_status": "pending",
  "reframe_suggestion": "<optional: safer wording if claim is overextended>"
}}

Return this JSON structure:
{{
  "chapter_number": {chapter_number},
  "total_claims": <int>,
  "high_risk_count": <int>,
  "claims": [<claim objects>],
  "risk_summary": "<one sentence overall assessment>"
}}"""

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

    # Save to memory/claims/
    output_dir = Path(__file__).parent / "memory" / "claims"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"claims_chapter_{chapter_number:02d}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n🔍 Claim Extractor — Chapter {chapter_number}")
    print(f"   Total Claims     : {result.get('total_claims', '?')}")
    print(f"   High Risk Claims : {result.get('high_risk_count', '?')}")
    print(f"   Risk Summary     : {result.get('risk_summary', '')}")
    print(f"   Saved to         : {output_path}")

    return result


if __name__ == "__main__":
    sample_chapter = """
    Chapter 2: What She's Actually Testing

    Women are not consciously running tests on men. But biologically and socially,
    they have developed powerful pattern recognition for character signals. Research
    shows that stated preferences in attraction differ significantly from real-time
    behavioral choices. Women consistently say they want sensitivity but respond more
    strongly to composure under pressure. A man who hesitates when a decision is
    required communicates more about his character than a hundred words of reassurance.
    Every man who gets stuck in the friend zone failed some version of this test
    without knowing there was one.
    """
    result = extract_claims(sample_chapter, chapter_number=2)
    print(json.dumps(result, indent=2))
