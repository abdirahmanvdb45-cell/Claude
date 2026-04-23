"""
Developmental Critic Agent — V3 Core Pipeline
Main quality checkpoint. Scores every chapter against strict criteria.
The drafter is never trusted as the final authority — this agent is.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"
CHAPTERS_DIR = Path(__file__).parent / "chapters"

# Hard rejection thresholds
REJECT_IF_BELOW = {"novelty": 7, "clarity": 7, "reader_value": 7, "structure": 7}
REJECT_IF_ABOVE = {"redundancy_risk": 4, "evidence_risk": 6}


def critique_chapter(chapter_number: int, chapter_text: str | None = None) -> dict:
    """
    Run developmental critique on a chapter draft.

    Args:
        chapter_number: The chapter to critique.
        chapter_text: Optional — if None, reads from chapters/chapter_draft_XX.md

    Returns:
        dict with scores, decision, must_fix, rewrite_instructions
        Saved to chapters/chapter_dev_report_XX.json
    """
    if chapter_text is None:
        draft_path = CHAPTERS_DIR / f"chapter_draft_{chapter_number:02d}.md"
        if not draft_path.exists():
            raise FileNotFoundError(f"No draft found for chapter {chapter_number}.")
        with open(draft_path) as f:
            chapter_text = f.read()

    packet_path = CHAPTERS_DIR / f"chapter_packet_{chapter_number:02d}.json"
    with open(packet_path) as f:
        packet = json.load(f)

    # Load prior chapter summaries for redundancy check
    summaries_path = MEMORY_DIR / "prior_chapter_summaries.json"
    prior_summaries = []
    if summaries_path.exists():
        with open(summaries_path) as f:
            prior_summaries = json.load(f)

    chapter_ledger = {}
    ledger_path = MEMORY_DIR / "chapter_ledger.json"
    if ledger_path.exists():
        with open(ledger_path) as f:
            chapter_ledger = json.load(f)

    system_prompt = """You are the Developmental Critic. You evaluate chapters like a strict
acquisitions editor who cares deeply about readers' time. You do not soften feedback.
A chapter that fails to deliver its promised new idea gets rejected. A chapter with
redundancy gets sent back. You are the system's main quality gate. Output valid JSON only."""

    user_prompt = f"""Critically evaluate Chapter {chapter_number}.

CHAPTER PACKET (the contract this chapter must fulfil):
{json.dumps(packet, indent=2)}

PRIOR CHAPTER CONTEXT (check for redundancy):
{json.dumps(prior_summaries, indent=2)}

CHAPTER LEDGER (concepts/metaphors/examples already used):
{json.dumps(chapter_ledger, indent=2)}

CHAPTER TEXT:
{chapter_text}

EVALUATION CRITERIA (score 1–10):
- novelty: Does this chapter introduce genuinely new value vs prior chapters?
- clarity: Is the argument understandable on first read?
- structure: Does it move logically from point to point?
- reader_value: Does the reader gain practical or conceptual value?
- redundancy_risk: How much does this overlap with prior chapters? (HIGHER = WORSE)
- tone_consistency: Does it match the established voice?
- evidence_risk: How many unsupported confident claims exist? (HIGHER = WORSE)

ADDITIONAL CHECKS:
- Did the chapter introduce its new idea within the first 20%?
- Did it fulfil the opening_job from the packet?
- Did it fulfil the closing_job from the packet?
- Did it include the required practical_takeaway?
- Does it stay within ±10% of the target word count ({packet.get('target_words', 3000)} words)?

Return this exact JSON:
{{
  "scores": {{
    "novelty": <float>,
    "clarity": <float>,
    "structure": <float>,
    "reader_value": <float>,
    "redundancy_risk": <float>,
    "tone_consistency": <float>,
    "evidence_risk": <float>
  }},
  "new_idea_introduced_early": <bool>,
  "opening_job_fulfilled": <bool>,
  "closing_job_fulfilled": <bool>,
  "practical_takeaway_present": <bool>,
  "word_count_check": "<within_range|too_short|too_long>",
  "decision": "<approve|rewrite|human_review>",
  "confidence": <float 0-1>,
  "must_fix": ["<specific issue that blocks approval>", ...],
  "optional_improvements": ["<suggestion not blocking approval>", ...],
  "redundancy_details": ["<specific repetition found>", ...],
  "rewrite_instructions": "<paragraph of specific rewrite guidance if decision is rewrite>"
}}

Decision rules:
- novelty < 7 → decision = "rewrite"
- clarity < 7 → decision = "rewrite"
- reader_value < 7 → decision = "rewrite"
- structure < 7 → decision = "rewrite"
- redundancy_risk > 4 → decision = "rewrite"
- evidence_risk > 6 → decision = "human_review"
- confidence < 0.65 → decision = "human_review" """

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

    # Enforce threshold rules
    scores = result.get("scores", {})
    for criterion, threshold in REJECT_IF_BELOW.items():
        if scores.get(criterion, 10) < threshold:
            result["decision"] = "rewrite"
            break
    for criterion, threshold in REJECT_IF_ABOVE.items():
        if scores.get(criterion, 0) > threshold:
            if criterion == "evidence_risk":
                result["decision"] = "human_review"
            else:
                result["decision"] = "rewrite"

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = CHAPTERS_DIR / f"chapter_dev_report_{chapter_number:02d}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n📝 Developmental Critic — Chapter {chapter_number}")
    for criterion, score in scores.items():
        flag = " ⚠️" if (
            (criterion in REJECT_IF_BELOW and score < REJECT_IF_BELOW[criterion]) or
            (criterion in REJECT_IF_ABOVE and score > REJECT_IF_ABOVE[criterion])
        ) else ""
        print(f"   {criterion:<22}: {score:.1f}{flag}")
    print(f"   Decision     : {result.get('decision', '?').upper()}")
    print(f"   Confidence   : {result.get('confidence', '?'):.0%}")
    if result.get("must_fix"):
        print("   Must Fix:")
        for fix in result["must_fix"]:
            print(f"     • {fix}")

    return result
