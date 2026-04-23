"""
Outline Architect Agent — V3 Core Pipeline
Builds a chapter progression that moves forward rather than circling the same thesis.
Every chapter must introduce one genuinely new idea. None may exist to restate the thesis.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"


def build_outline(book_brief: dict, premise_report: dict, market_map: dict | None = None) -> dict:
    """
    Build the locked chapter outline.

    Args:
        book_brief: Approved book brief dict.
        premise_report: Premise stress test results (used to avoid flagged collision areas).
        market_map: Optional market research dict.

    Returns:
        dict — saved to memory/outline.json
    """
    collision_warnings = premise_report.get("chapter_collision_warnings", [])
    warnings_text = "\n".join(f"- {w}" for w in collision_warnings) if collision_warnings else "None identified."

    market_text = json.dumps(market_map, indent=2) if market_map else "Not provided."

    system_prompt = """You are the Outline Architect. You build nonfiction chapter structures
that actually progress. You think structurally, not poetically. Every chapter must earn its
place by introducing something the reader cannot get from any other chapter. Output valid JSON only."""

    user_prompt = f"""Build the complete chapter outline for this book.

BOOK BRIEF:
{json.dumps(book_brief, indent=2)}

PREMISE REPORT — COLLISION WARNINGS (avoid these overlaps):
{warnings_text}

MARKET MAP:
{market_text}

Rules:
- every chapter introduces ONE genuinely new idea
- every chapter moves the reader forward (new understanding, not just new examples)
- no chapter may exist to restate the thesis
- explicitly list what each chapter MUST NOT repeat from prior chapters
- identify dependencies (which chapters require prior chapters to be understood)
- optimize for progression, not symmetry
- opening and closing functions must be distinct for every chapter

Return this exact JSON schema:
{{
  "parts": [
    {{
      "name": "<part name, e.g. 'Part One: The Foundation'>",
      "purpose": "<what this part achieves>",
      "chapters": [
        {{
          "number": <int>,
          "title": "<chapter title>",
          "purpose": "<what job this chapter does in the book>",
          "reader_shift": "<how the reader thinks/feels differently after this chapter>",
          "new_idea": "<the ONE idea introduced here, stated precisely>",
          "depends_on": [<chapter numbers this chapter builds on>],
          "must_not_repeat": ["<concept or example from prior chapters that must not reappear>"],
          "practical_payoff": "<what the reader can do or understand after this chapter>",
          "evidence_needs": ["<any research or data this chapter will need>"],
          "opening_job": "<what the opening must achieve>",
          "closing_job": "<what the closing must leave the reader with>",
          "target_words": <int>
        }}
      ]
    }}
  ],
  "global_repetition_risks": ["<cross-chapter risk>", ...],
  "outline_notes": ["<note>", ...]
}}"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_DIR / "outline.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Count chapters across all parts
    total_chapters = sum(len(part.get("chapters", [])) for part in result.get("parts", []))
    print(f"\n🗂  Outline Architect — Outline Created")
    print(f"   Parts    : {len(result.get('parts', []))}")
    print(f"   Chapters : {total_chapters}")
    for part in result.get("parts", []):
        print(f"\n   {part.get('name', '')}: {part.get('purpose', '')}")
        for ch in part.get("chapters", []):
            print(f"     Ch {ch.get('number', '?')}: {ch.get('title', '')} — {ch.get('new_idea', '')}")

    return result


def critique_outline(outline: dict, book_brief: dict) -> dict:
    """
    Run the Developmental Critic in outline mode.
    Checks for overlap, weak chapter purpose, duplicate transformations, filler chapters.

    Returns:
        dict with issues, gate decision — saved to memory/outline_review.json
    """
    system_prompt = """You are the Developmental Critic reviewing a chapter outline.
Your job is to find structural problems before a single word of prose is written.
You are strict. A chapter that cannot justify its own existence must be flagged.
Output valid JSON only."""

    # Extract chapter summaries for comparison
    chapters = []
    for part in outline.get("parts", []):
        chapters.extend(part.get("chapters", []))

    chapters_text = json.dumps(chapters, indent=2)

    user_prompt = f"""Critique this chapter outline for the book defined by the following brief.

BOOK BRIEF THESIS: {book_brief.get('book_thesis', '')}
BOOK BRIEF PROMISE: {book_brief.get('core_promise', '')}

CHAPTERS:
{chapters_text}

Check for:
1. Any two chapters with the same or nearly identical "new_idea" → REJECT immediately
2. Chapters whose "purpose" is just to restate the thesis
3. Chapters where the "reader_shift" is indistinguishable from another chapter
4. Filler chapters that exist for structural symmetry, not content necessity
5. Missing practical sections (does every chapter have a real payoff?)
6. Weak sequencing (would a different order serve the reader better?)
7. Dependency gaps (does a chapter assume knowledge not yet established?)

Return this JSON:
{{
  "duplicate_ideas_found": <bool>,
  "duplicate_pairs": [
    {{"chapter_a": <int>, "chapter_b": <int>, "overlap": "<what overlaps>"}}
  ],
  "filler_chapters": [<chapter numbers>],
  "weak_chapters": [
    {{"chapter": <int>, "issue": "<what's weak>"}}
  ],
  "sequencing_issues": ["<issue>"],
  "dependency_gaps": ["<gap>"],
  "overall_issues": ["<issue>"],
  "gate_decision": "<approve|revise|reject>",
  "revision_instructions": ["<specific change required>", ...]
}}

Gate rules:
- ANY duplicate new_idea → gate_decision = "reject" (must rebuild)
- Filler chapters present → gate_decision = "revise"
- All clear → gate_decision = "approve" """

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

    with open(MEMORY_DIR / "outline_review.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n🔎 Outline Critique")
    print(f"   Duplicate Ideas   : {'YES — REJECT' if result.get('duplicate_ideas_found') else 'None found'}")
    print(f"   Filler Chapters   : {result.get('filler_chapters', [])}")
    print(f"   Gate Decision     : {result.get('gate_decision', '?').upper()}")

    return result


def lock_outline(outline: dict) -> dict:
    """
    Write the locked outline to memory/outline_locked.json.
    No downstream agent may modify this file directly.
    """
    with open(MEMORY_DIR / "outline_locked.json", "w", encoding="utf-8") as f:
        json.dump(outline, f, indent=2)
    print("\n🔒 Outline locked. No downstream agent may modify outline_locked.json.")
    return outline
