"""
Line Editor Agent — V3 Core Pipeline
Makes approved chapter drafts readable and clean without changing structure or argument.
Rhythm, clarity, transitions, repeated wording, overwritten passages.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"
CHAPTERS_DIR = Path(__file__).parent / "chapters"


def line_edit_chapter(chapter_number: int, chapter_text: str | None = None) -> str:
    """
    Line edit an approved chapter draft.

    Args:
        chapter_number: The chapter to edit.
        chapter_text: Optional text. If None, reads from chapter_draft_XX.md.

    Returns:
        Polished chapter text as markdown. Saved to chapter_polished_XX.md.
    """
    if chapter_text is None:
        draft_path = CHAPTERS_DIR / f"chapter_draft_{chapter_number:02d}.md"
        with open(draft_path) as f:
            chapter_text = f.read()

    voice_bible_path = MEMORY_DIR / "voice_bible.json"
    voice_bible = {}
    if voice_bible_path.exists():
        with open(voice_bible_path) as f:
            voice_bible = json.load(f)

    system_prompt = f"""You are the Line Editor. You improve prose quality without changing
structure or argument. You are not here to rewrite the chapter — you are here to make it
cleaner, sharper, and more readable. You do not add new arguments or examples.
VOICE PROFILE: {voice_bible.get('voice_profile', 'plainspoken peer-level nonfiction')}"""

    user_prompt = f"""Line edit Chapter {chapter_number}.

CHAPTER TEXT:
{chapter_text}

VOICE RULES:
Sentence rules: {json.dumps(voice_bible.get('sentence_rules', []))}
Paragraph rules: {json.dumps(voice_bible.get('paragraph_rules', []))}
Forbidden phrases: {json.dumps(voice_bible.get('forbidden_phrases', []))}

LINE EDITING FOCUS:
1. Rhythm — vary sentence length deliberately; break monotony
2. Clarity — simplify overwritten or convoluted passages
3. Transitions — smooth any abrupt jumps between sections
4. Remove repeated wording within the same or adjacent paragraphs
5. Tighten overwritten passages — say the same thing in fewer words
6. Fix any remaining forbidden phrases
7. Ensure paragraph length is consistent with the voice bible

DO NOT:
- Add new examples, arguments, or claims
- Change the chapter's structure or section order
- Increase drama or raise the emotional register artificially
- Change the opening or closing beyond prose tightening
- Add anything the drafter did not include

Output the polished chapter in markdown only. No preamble, no editorial notes."""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    polished = response.content[0].text.strip()

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    polished_path = CHAPTERS_DIR / f"chapter_polished_{chapter_number:02d}.md"
    with open(polished_path, "w", encoding="utf-8") as f:
        f.write(polished)

    print(f"\n✨ Line Editor — Chapter {chapter_number}")
    print(f"   Words before : {len(chapter_text.split()):,}")
    print(f"   Words after  : {len(polished.split()):,}")
    print(f"   Saved        : {polished_path}")

    return polished


def update_memory_after_chapter(chapter_number: int, polished_text: str):
    """
    Update all memory files after a chapter is approved and polished.
    This is mandatory — no chapter pipeline is complete without this step.

    Updates:
    - chapter_ledger.json
    - concept_ledger.json
    - prior_chapter_summaries.json
    - run_state.json
    """
    voice_bible_path = MEMORY_DIR / "voice_bible.json"
    voice_bible = {}
    if voice_bible_path.exists():
        with open(voice_bible_path) as f:
            voice_bible = json.load(f)

    system_prompt = """You are the Memory Updater. You read approved chapters and extract
structured records of what was established, used, and defined. This memory prevents all
future chapters from repeating material. Output valid JSON only."""

    user_prompt = f"""Analyse this approved chapter and extract memory records.

CHAPTER NUMBER: {chapter_number}

CHAPTER TEXT:
{polished_text}

Extract:
1. new_concepts: New ideas or terms defined for the first time
2. metaphors_used: Any metaphors or analogies used (even once)
3. examples_used: Named examples, case studies, or scenarios
4. claims_added: Factual or research-sensitive claims made
5. do_not_repeat_next: Specific instructions for subsequent chapters

Also write:
6. chapter_summary: 3–5 sentence summary for the prior_chapter_summaries file

Return this JSON:
{{
  "chapter_number": {chapter_number},
  "new_concepts": ["<concept>", ...],
  "metaphors_used": ["<metaphor>", ...],
  "examples_used": ["<example name>", ...],
  "claims_added": ["<claim>", ...],
  "do_not_repeat_next": ["<specific instruction>", ...],
  "chapter_summary": "<3-5 sentence summary>"
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
    memory_record = json.loads(raw.strip())

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # Update chapter_ledger.json
    ledger_path = MEMORY_DIR / "chapter_ledger.json"
    try:
        with open(ledger_path) as f:
            ledger = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ledger = {"chapters": {}}

    ledger["chapters"][str(chapter_number)] = {
        "new_concepts": memory_record.get("new_concepts", []),
        "metaphors_used": memory_record.get("metaphors_used", []),
        "examples_used": memory_record.get("examples_used", []),
        "claims_added": memory_record.get("claims_added", []),
        "do_not_repeat_next": memory_record.get("do_not_repeat_next", []),
    }
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

    # Update concept_ledger.json
    concept_path = MEMORY_DIR / "concept_ledger.json"
    try:
        with open(concept_path) as f:
            concepts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        concepts = {"defined_concepts": []}

    for concept in memory_record.get("new_concepts", []):
        if concept not in concepts["defined_concepts"]:
            concepts["defined_concepts"].append(concept)
    with open(concept_path, "w", encoding="utf-8") as f:
        json.dump(concepts, f, indent=2)

    # Update prior_chapter_summaries.json
    summaries_path = MEMORY_DIR / "prior_chapter_summaries.json"
    try:
        with open(summaries_path) as f:
            summaries = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        summaries = []

    summaries.append({
        "chapter_number": chapter_number,
        "summary": memory_record.get("chapter_summary", ""),
        "do_not_repeat": memory_record.get("do_not_repeat_next", []),
    })
    with open(summaries_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

    print(f"\n🧩 Memory Updated for Chapter {chapter_number}")
    print(f"   New concepts    : {memory_record.get('new_concepts', [])}")
    print(f"   Metaphors used  : {memory_record.get('metaphors_used', [])}")
    print(f"   Examples used   : {memory_record.get('examples_used', [])}")

    return memory_record
