"""
Book Strategist Agent — V3 Core Pipeline
Creates the commercial/editorial book brief — the most important planning artifact.
Also generates the voice bible. All downstream agents depend on this output.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"


def create_book_brief(normalized_input: dict, market_map: dict | None = None) -> dict:
    """
    Create the master book brief from normalized input and optional market research.

    This is the single most important artifact in the system.
    If this is weak, every chapter will be weak.

    Returns:
        dict — saved to memory/book_brief.json
    """
    market_text = json.dumps(market_map, indent=2) if market_map else "Not yet available."

    system_prompt = """You are the Book Strategist. You define books with commercial precision.
You write briefs that give every downstream agent an unambiguous target. You never write vague promises.
You think like a publisher who has seen ten thousand bad proposals. Output valid JSON only."""

    user_prompt = f"""Create the master book brief for this project.

NORMALIZED INPUT:
{json.dumps(normalized_input, indent=2)}

MARKET MAP:
{market_text}

This brief will govern every chapter this system writes. Make it exact.

Return this exact JSON schema:
{{
  "working_title": "<draft title>",
  "subtitle_options": ["<option 1>", "<option 2>", "<option 3>"],
  "reader_avatar": "<precise single-sentence reader description>",
  "reader_problem": "<the specific problem the reader has right now>",
  "reader_desired_outcome": "<what the reader wants to achieve>",
  "core_promise": "<the one thing this book delivers — must be specific>",
  "book_thesis": "<the central argument in one sentence>",
  "unique_angle": "<what makes this different from existing books on the topic>",
  "scope_in": ["<what belongs in this book>", ...],
  "scope_out": ["<what does NOT belong>", ...],
  "tone_rules": ["<rule>", ...],
  "must_include": ["<element>", ...],
  "must_avoid": ["<element>", ...],
  "evidence_sensitive_areas": ["<area>", ...],
  "chapter_count_target": <int>,
  "word_count_target": <int>,
  "comparable_books": ["<title by author>", ...]
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

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_DIR / "book_brief.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n📚 Book Strategist — Brief Created")
    print(f"   Title     : {result.get('working_title', '')}")
    print(f"   Thesis    : {result.get('book_thesis', '')}")
    print(f"   Promise   : {result.get('core_promise', '')}")
    print(f"   Chapters  : {result.get('chapter_count_target', '?')}")

    return result


def create_voice_bible(book_brief: dict) -> dict:
    """
    Generate the voice and style bible from the approved book brief.
    Saved to memory/voice_bible.json — read by every drafting agent.
    """
    system_prompt = """You are the Voice Architect. You write precise voice bibles that tell
drafting agents exactly how to write — not what to say, but how to say it.
A good voice bible prevents tone drift across chapters. Output valid JSON only."""

    user_prompt = f"""Create the voice and style bible for this book.

BOOK BRIEF:
{json.dumps(book_brief, indent=2)}

Return this exact JSON:
{{
  "voice_profile": "<one phrase describing the voice — e.g. 'plainspoken peer-level nonfiction'>",
  "tone_rules": [
    "<rule — e.g. 'write to a smart friend, not a student'>",
    ...
  ],
  "sentence_rules": [
    "<rule — e.g. 'vary sentence length deliberately'>",
    ...
  ],
  "paragraph_rules": [
    "<rule — e.g. 'max 4 lines per paragraph in most cases'>",
    ...
  ],
  "forbidden_phrases": [
    "<phrase to never use>",
    ...
  ],
  "forbidden_structures": [
    "<structural pattern to avoid>",
    ...
  ],
  "allowed_devices": [
    "<allowed stylistic device and its constraint>",
    ...
  ],
  "opening_rules": [
    "<rule for how chapters must open>",
    ...
  ],
  "closing_rules": [
    "<rule for how chapters must close>",
    ...
  ],
  "example_of_correct_voice": "<2–3 sentences in the correct voice>",
  "example_of_incorrect_voice": "<2–3 sentences in the wrong voice>"
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

    with open(MEMORY_DIR / "voice_bible.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n🗣  Voice Bible Created")
    print(f"   Profile: {result.get('voice_profile', '')}")
    print(f"   Forbidden phrases: {len(result.get('forbidden_phrases', []))}")

    return result


def create_banned_patterns() -> dict:
    """Initialize banned_patterns.json with structural anti-patterns."""
    banned = {
        "do_not_emit": [
            "TITLE",
            "duplicate chapter intros",
            "restating the thesis in every opening paragraph",
            "same anecdote reused in multiple chapters without explicit permission",
            "same metaphor more than twice in one chapter",
            "faux-profound one-line paragraphs used repeatedly",
            "coach-speak: 'unlock', 'transform', 'journey', 'game changer'",
            "placeholder text of any kind",
            "summaries of what the book will cover inserted mid-chapter",
        ],
        "structural_bans": [
            "do not open a chapter by describing what the chapter is about",
            "do not close a chapter with a list of everything the chapter covered",
            "do not introduce a concept and then wait until the next paragraph to define it",
            "do not use rhetorical questions as a substitute for making a point",
        ],
    }

    with open(MEMORY_DIR / "banned_patterns.json", "w", encoding="utf-8") as f:
        json.dump(banned, f, indent=2)

    print("   Banned patterns file initialised.")
    return banned
