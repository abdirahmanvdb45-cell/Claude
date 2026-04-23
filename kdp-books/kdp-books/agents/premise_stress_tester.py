"""
Premise Stress Tester Agent — V3 Core Pipeline
Attacks the book idea before drafting begins.
Catches weak premises, repetition risk, unsupported claims, and scope problems.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"

# Routing thresholds
BOOKWORTHINESS_MIN = 7.0
REPETITION_RISK_MAX = 5.0
MARKET_DISTINCTIVENESS_MIN = 6.0


def stress_test_premise(book_brief: dict) -> dict:
    """
    Attack the book brief to find weaknesses before committing to drafting.

    Args:
        book_brief: The approved book brief dict.

    Returns:
        dict with scores, flaws, required changes, and go/no-go decision.
        Saved to memory/premise_report.json
    """
    system_prompt = """You are the Premise Stress Tester. Your job is to challenge a book brief
brutally and intelligently — before any writing happens. You think like a sceptical acquisitions
editor who has rejected 95% of proposals they've received. You are not trying to kill good ideas;
you are trying to save the system from producing 50,000 words of weak content.
Output valid JSON only."""

    user_prompt = f"""Stress-test this book brief. Attack it from every angle.

BOOK BRIEF:
{json.dumps(book_brief, indent=2)}

Look for these failure modes:
1. Repetition risk — will chapters become circular and restate the same point?
2. Weak differentiation — does this feel like a hundred books that already exist?
3. Thesis inflation — is the core argument bigger than the evidence can support?
4. Scope creep — is the promise too large for the chapter count?
5. Evidence risk — does the book depend on overconfident psychological or scientific claims?
6. Bookworthiness — could this idea be a blog post instead of a full book?
7. Chapter collision risk — will chapters inevitably overlap?

Score each dimension 1–10:
- premise_strength: Is the central thesis strong and defensible?
- market_distinctiveness: Does this stand out from comparable books?
- repetition_risk: Higher score = MORE risk of circular content (bad)
- evidence_risk: Higher score = MORE risk of unsupported claims (bad)
- bookworthiness: Is this genuinely a full book?
- scope_manageability: Can the chapter count actually deliver the promise?

Return this exact JSON:
{{
  "scores": {{
    "premise_strength": <float 1-10>,
    "market_distinctiveness": <float 1-10>,
    "repetition_risk": <float 1-10>,
    "evidence_risk": <float 1-10>,
    "bookworthiness": <float 1-10>,
    "scope_manageability": <float 1-10>
  }},
  "fatal_flaws": ["<flaw that must be fixed before proceeding>", ...],
  "salvageable_flaws": ["<flaw that can be fixed in the outline>", ...],
  "required_changes": ["<specific change required>", ...],
  "chapter_collision_warnings": ["<which chapter areas will overlap>", ...],
  "evidence_watch_areas": ["<topic area needing careful handling>", ...],
  "go_no_go": "<go|revise|no_go>",
  "stress_test_verdict": "<two sentence summary of findings>"
}}

Decision rules:
- bookworthiness < 7.0 OR repetition_risk > 5.0 → go_no_go = "revise" (route back to Book Strategist)
- market_distinctiveness < 6.0 → go_no_go = "revise"
- fatal_flaws present → go_no_go = "no_go" if unfixable, "revise" if fixable
- all scores passing → go_no_go = "go" """

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

    # Apply threshold rules
    scores = result.get("scores", {})
    if (
        scores.get("bookworthiness", 10) < BOOKWORTHINESS_MIN
        or scores.get("repetition_risk", 0) > REPETITION_RISK_MAX
        or scores.get("market_distinctiveness", 10) < MARKET_DISTINCTIVENESS_MIN
    ):
        result["go_no_go"] = "revise"

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_DIR / "premise_report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n🔬 Premise Stress Tester")
    print(f"   Bookworthiness       : {scores.get('bookworthiness', '?'):.1f}")
    print(f"   Market Distinctiveness: {scores.get('market_distinctiveness', '?'):.1f}")
    print(f"   Repetition Risk      : {scores.get('repetition_risk', '?'):.1f}")
    print(f"   Decision             : {result.get('go_no_go', '?').upper()}")
    if result.get("fatal_flaws"):
        print("   Fatal Flaws:")
        for flaw in result["fatal_flaws"]:
            print(f"     ✗ {flaw}")
    if result.get("required_changes"):
        print("   Required Changes:")
        for change in result["required_changes"]:
            print(f"     → {change}")

    return result
