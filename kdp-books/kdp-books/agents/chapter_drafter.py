"""
Chapter Drafter & Rewriter Agent — V3 Core Pipeline
Writes chapter prose strictly from the chapter packet.
Never trusted as the final authority on quality — all output goes through the critic.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"
CHAPTERS_DIR = Path(__file__).parent / "chapters"

MAX_REVISIONS = 3


def _load_memory_file(filename: str) -> dict:
    path = MEMORY_DIR / filename
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def draft_chapter(chapter_number: int) -> str:
    """
    Draft a chapter from its approved packet.
    The drafter obeys the packet. It does not improvise.

    Args:
        chapter_number: Chapter to draft.

    Returns:
        Chapter text as markdown string. Saved to chapters/chapter_draft_XX.md
    """
    packet_path = CHAPTERS_DIR / f"chapter_packet_{chapter_number:02d}.json"
    if not packet_path.exists():
        raise FileNotFoundError(f"No packet found for chapter {chapter_number}. Run chapter_planner first.")

    with open(packet_path, encoding="utf-8") as f:
        packet = json.load(f)

    if packet.get("gate_violation"):
        raise ValueError(f"Chapter {chapter_number} packet has a gate violation: {packet['gate_violation']}")

    voice_bible = _load_memory_file("voice_bible.json")
    banned_patterns = _load_memory_file("banned_patterns.json")
    book_brief = _load_memory_file("book_brief.json")

    system_prompt = f"""You are the Chapter Drafter. You write nonfiction chapters from exact packets.
You obey the packet. You do not improvise, add new arguments, or stray from the chapter goal.
The packet is a contract; your output must fulfil it precisely.

VOICE PROFILE: {voice_bible.get('voice_profile', 'plainspoken peer-level nonfiction')}

FORBIDDEN PHRASES: {json.dumps(voice_bible.get('forbidden_phrases', []))}
BANNED STRUCTURES: {json.dumps(banned_patterns.get('structural_bans', []))}
DO NOT EMIT: {json.dumps(banned_patterns.get('do_not_emit', []))}"""

    user_prompt = f"""Write Chapter {chapter_number} using this packet.

CHAPTER PACKET:
{json.dumps(packet, indent=2)}

BOOK THESIS (stay aligned): {book_brief.get('book_thesis', '')}
READER AVATAR: {book_brief.get('reader_avatar', '')}

WRITING RULES:
1. Introduce the new idea within the first 20% of the chapter
2. Develop it with fresh material — no repeating what prior chapters established
3. Include every required section and example from the packet
4. Do NOT use placeholder text of any kind
5. Do NOT summarise the whole book
6. Include the practical payoff exactly as specified in the packet
7. End according to the closing_job in the packet
8. Stay within ±10% of target word count ({packet.get('target_words', 3000)} words)
9. Write in markdown with ## for section headings

Output the chapter text in markdown only. No preamble, no notes."""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    chapter_text = response.content[0].text.strip()

    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = CHAPTERS_DIR / f"chapter_draft_{chapter_number:02d}.md"
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(chapter_text)

    word_count = len(chapter_text.split())
    print(f"\n✍️  Chapter Drafter — Chapter {chapter_number} Draft")
    print(f"   Words  : {word_count:,} (target: {packet.get('target_words', '?'):,})")
    print(f"   Saved  : {draft_path}")

    return chapter_text


def rewrite_chapter(chapter_number: int, revision_count: int = 0) -> str:
    """
    Rewrite a chapter based on the developmental critic's report.
    Max 3 revisions — after that, escalate to human review.

    Args:
        chapter_number: Chapter to rewrite.
        revision_count: Current revision count (system enforces MAX_REVISIONS).

    Returns:
        Rewritten chapter text as markdown.
    """
    if revision_count >= MAX_REVISIONS:
        raise RuntimeError(
            f"Chapter {chapter_number} has reached max revisions ({MAX_REVISIONS}). "
            "Routing to human review."
        )

    # Load the dev report and previous draft
    dev_report_path = CHAPTERS_DIR / f"chapter_dev_report_{chapter_number:02d}.json"
    draft_path = CHAPTERS_DIR / f"chapter_draft_{chapter_number:02d}.md"
    packet_path = CHAPTERS_DIR / f"chapter_packet_{chapter_number:02d}.json"

    if not dev_report_path.exists():
        raise FileNotFoundError(f"No dev report for chapter {chapter_number}. Run developmental critic first.")

    with open(dev_report_path, encoding="utf-8") as f:
        dev_report = json.load(f)
    with open(draft_path, encoding="utf-8") as f:
        previous_draft = f.read()
    with open(packet_path, encoding="utf-8") as f:
        packet = json.load(f)

    voice_bible = _load_memory_file("voice_bible.json")

    system_prompt = f"""You are the Chapter Rewriter. You fix only what the critic flagged.
You do not widen scope. You do not add new claims. You remove redundancy first, strengthen fresh
material second. VOICE: {voice_bible.get('voice_profile', 'plainspoken peer-level nonfiction')}"""

    user_prompt = f"""Rewrite Chapter {chapter_number} based on the critic's report.

CRITIC REPORT:
{json.dumps(dev_report, indent=2)}

CHAPTER PACKET (the contract — do not deviate from chapter_goal):
{json.dumps({{k: packet.get(k) for k in ['chapter_goal', 'this_chapter_adds', 'practical_takeaway', 'opening_job', 'closing_job', 'target_words']}}, indent=2)}

PREVIOUS DRAFT:
{previous_draft}

REWRITE RULES:
1. Fix ONLY the issues listed in must_fix
2. Preserve all content that scored well
3. Remove redundancy first
4. Strengthen fresh material second
5. Do NOT add new unsupported claims
6. Do NOT widen the chapter's scope
7. Maintain the voice — use the closing_job and opening_job from the packet
8. Stay within ±10% of {packet.get('target_words', 3000)} words

Output the rewritten chapter in markdown only."""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    rewritten = response.content[0].text.strip()
    revision_number = revision_count + 1

    rewrite_path = CHAPTERS_DIR / f"chapter_rewrite_{chapter_number:02d}_v{revision_number}.md"
    with open(rewrite_path, "w", encoding="utf-8") as f:
        f.write(rewritten)

    # Also update the main draft file
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(rewritten)

    print(f"\n🔄 Chapter Rewriter — Chapter {chapter_number} (Revision {revision_number}/{MAX_REVISIONS})")
    print(f"   Words  : {len(rewritten.split()):,}")
    print(f"   Saved  : {rewrite_path}")

    return rewritten
