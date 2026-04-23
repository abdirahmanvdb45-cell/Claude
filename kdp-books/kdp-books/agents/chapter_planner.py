"""
Chapter Planner Agent — V3 Core Pipeline
Converts one approved outline chapter into a strict chapter packet.
No chapter is EVER drafted without a packet. The packet is the contract the drafter must obey.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"
CHAPTERS_DIR = Path(__file__).parent / "chapters"


def _load_memory_file(filename: str) -> dict | list:
    path = MEMORY_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _get_prior_chapter_summaries() -> list[dict]:
    summaries_path = MEMORY_DIR / "prior_chapter_summaries.json"
    if summaries_path.exists():
        with open(summaries_path) as f:
            return json.load(f)
    return []


def build_chapter_packet(chapter_number: int) -> dict:
    """
    Build a chapter packet for the specified chapter number.
    Reads from locked outline, chapter ledger, concept ledger, voice bible, banned patterns.

    Args:
        chapter_number: The chapter to build a packet for.

    Returns:
        dict — saved to chapters/chapter_packet_XX.json
    """
    outline = _load_memory_file("outline_locked.json")
    book_brief = _load_memory_file("book_brief.json")
    chapter_ledger = _load_memory_file("chapter_ledger.json")
    concept_ledger = _load_memory_file("concept_ledger.json")
    voice_bible = _load_memory_file("voice_bible.json")
    banned_patterns = _load_memory_file("banned_patterns.json")
    prior_summaries = _get_prior_chapter_summaries()

    # Find this chapter in the locked outline
    target_chapter = None
    for part in outline.get("parts", []):
        for ch in part.get("chapters", []):
            if ch.get("number") == chapter_number:
                target_chapter = ch
                break
        if target_chapter:
            break

    if not target_chapter:
        raise ValueError(f"Chapter {chapter_number} not found in locked outline.")

    # Build prior context summary
    prior_context = []
    for ch_num in target_chapter.get("depends_on", []):
        ledger = chapter_ledger.get("chapters", {}).get(str(ch_num), {})
        if ledger:
            prior_context.append(f"Ch {ch_num}: established concepts {ledger.get('new_concepts', [])}, used metaphors {ledger.get('metaphors_used', [])}")

    system_prompt = """You are the Chapter Planner. You turn one approved outline entry into
a precise, detailed chapter packet. The packet is a contract. The drafter must follow it exactly.
You do not write prose. You write instructions. Output valid JSON only."""

    user_prompt = f"""Build the chapter packet for Chapter {chapter_number}.

OUTLINE ENTRY FOR THIS CHAPTER:
{json.dumps(target_chapter, indent=2)}

BOOK BRIEF (thesis, promise, tone):
{json.dumps({{k: book_brief.get(k) for k in ['book_thesis', 'core_promise', 'tone_rules', 'must_avoid']}}, indent=2)}

PRIOR CHAPTER CONTEXT (what has already been established):
{json.dumps(prior_context, indent=2)}

CHAPTER LEDGER — concepts/metaphors/examples already used:
{json.dumps(chapter_ledger, indent=2)}

CONCEPT LEDGER — all defined terms so far:
{json.dumps(concept_ledger, indent=2)}

BANNED PATTERNS:
{json.dumps(banned_patterns, indent=2)}

VOICE BIBLE (key rules only):
Forbidden phrases: {json.dumps(voice_bible.get('forbidden_phrases', []))}
Sentence rules: {json.dumps(voice_bible.get('sentence_rules', []))}

Build the packet. Be specific. Do not write prose.

Return this exact schema:
{{
  "chapter_number": {chapter_number},
  "chapter_title": "<title from outline>",
  "chapter_goal": "<precise statement of what this chapter must achieve>",
  "reader_already_knows": ["<concept established in prior chapters>", ...],
  "this_chapter_adds": ["<new concept or insight this chapter introduces>", ...],
  "required_sections": [
    {{
      "section_title": "<section name>",
      "section_job": "<what this section must do>",
      "section_content_notes": "<specific guidance>"
    }}
  ],
  "required_examples": ["<example that must appear — be specific>", ...],
  "optional_examples": ["<example that can be used if useful>", ...],
  "forbidden_repetitions": ["<concept/example from prior chapters that CANNOT reappear>", ...],
  "forbidden_metaphors": ["<metaphors already used that cannot be repeated>", ...],
  "practical_takeaway": "<specific reader action or understanding — not vague>",
  "evidence_notes": ["<any research claim that needs careful handling>", ...],
  "opening_job": "<exactly what the opening 200 words must do>",
  "closing_job": "<exactly what the final 200 words must leave the reader with>",
  "target_words": <int>,
  "hard_stops": ["<condition that makes this chapter fail automatically>", ...]
}}

Gate rule: if "this_chapter_adds" is empty or duplicates a concept in the chapter ledger,
add a "gate_violation" key explaining the problem."""

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

    # Gate check
    if not result.get("this_chapter_adds"):
        result["gate_violation"] = "this_chapter_adds is empty — chapter has no new content to justify its existence"

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    packet_path = CHAPTERS_DIR / f"chapter_packet_{chapter_number:02d}.json"
    with open(packet_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n📦 Chapter Planner — Packet for Chapter {chapter_number}")
    print(f"   Title      : {result.get('chapter_title', '')}")
    print(f"   Goal       : {result.get('chapter_goal', '')}")
    print(f"   Adds       : {result.get('this_chapter_adds', [])}")
    if result.get("gate_violation"):
        print(f"   ⛔ GATE VIOLATION: {result['gate_violation']}")

    return result
