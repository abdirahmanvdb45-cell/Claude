"""
Continuity Editor Agent — V3 Core Pipeline
Audits the full manuscript after all chapters are drafted.
Catches repeated openings, duplicate examples, concept drift, voice inconsistency.
Any flagged chapter is routed back through the rewrite loop before assembly.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR = Path(__file__).parent / "memory"
CHAPTERS_DIR = Path(__file__).parent / "chapters"
OUTPUT_DIR = Path(__file__).parent / "output"


def _load_all_polished_chapters() -> dict[int, str]:
    """Load all approved polished chapter files."""
    chapters = {}
    for path in sorted(CHAPTERS_DIR.glob("chapter_polished_*.md")):
        num = int(path.stem.split("_")[-1])
        with open(path) as f:
            chapters[num] = f.read()
    return chapters


def continuity_pass() -> dict:
    """
    Audit the complete manuscript for continuity issues.

    Returns:
        dict with global_issues, chapter_flags, duplicate_map, required_rewrites, final_status
        Saved to output/continuity_report.json
    """
    chapters = _load_all_polished_chapters()

    if not chapters:
        raise FileNotFoundError("No polished chapters found. Run line_editor for all chapters first.")

    chapter_ledger = {}
    ledger_path = MEMORY_DIR / "chapter_ledger.json"
    if ledger_path.exists():
        with open(ledger_path) as f:
            chapter_ledger = json.load(f)

    book_brief = {}
    brief_path = MEMORY_DIR / "book_brief.json"
    if brief_path.exists():
        with open(brief_path) as f:
            book_brief = json.load(f)

    # Build compact chapter digest for the prompt (avoid token overflow)
    chapter_digest = {}
    for num, text in chapters.items():
        words = text.split()
        opening = " ".join(words[:80])
        closing = " ".join(words[-80:])
        chapter_digest[num] = {
            "opening_100_words": opening,
            "closing_100_words": closing,
            "word_count": len(words),
        }

    system_prompt = """You are the Continuity Editor. You audit full nonfiction manuscripts for
structural and stylistic problems that span chapters. You are looking for patterns that damage
the book as a whole — not individual chapter quality, which the developmental critic already handled.
Output valid JSON only."""

    user_prompt = f"""Audit the manuscript for continuity problems.

BOOK THESIS: {book_brief.get('book_thesis', '')}

CHAPTER LEDGER (all concepts, metaphors, examples used per chapter):
{json.dumps(chapter_ledger, indent=2)}

CHAPTER DIGEST (opening and closing of each chapter):
{json.dumps(chapter_digest, indent=2)}

CHECK FOR:
1. Repeated openings — do 2+ chapters open with the same type of statement?
2. Repeated examples — is the same named example used in multiple chapters?
3. Chapter overlap — do 2+ chapters make substantively the same point?
4. Term inconsistency — is the same concept named differently across chapters?
5. Voice drift — do later chapters sound different from earlier chapters?
6. False escalation — does every chapter claim to be "the most important thing"?
7. Missing bridges — are there jumps between chapters that will confuse readers?
8. Repeated emotional beats — does the same emotional arc repeat?
9. Unresolved promises — does the book set up anything it doesn't pay off?
10. Chapter order — would a different sequence serve the reader better?

Return this JSON:
{{
  "global_issues": ["<issue affecting the whole manuscript>", ...],
  "chapter_flags": [
    {{
      "chapter": <int>,
      "issue": "<what's wrong>",
      "severity": "<low|medium|high>",
      "rewrite_instruction": "<specific fix>"
    }}
  ],
  "duplicate_map": [
    {{
      "type": "<opening|example|concept|emotional_beat>",
      "chapters_involved": [<int>, <int>],
      "description": "<what duplicates>"
    }}
  ],
  "term_inconsistencies": [
    {{
      "concept": "<what concept>",
      "chapter_a_name": "<how ch A calls it>",
      "chapter_b_name": "<how ch B calls it>"
    }}
  ],
  "required_rewrites": [<chapter numbers that must go back through rewrite loop>],
  "final_status": "<clean|revisions_required>",
  "assembler_instructions": "<any special notes for the assembly step>"
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

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "continuity_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n🔗 Continuity Editor — Full Manuscript Audit")
    print(f"   Global Issues    : {len(result.get('global_issues', []))}")
    print(f"   Chapter Flags    : {len(result.get('chapter_flags', []))}")
    print(f"   Duplicates Found : {len(result.get('duplicate_map', []))}")
    print(f"   Rewrites Needed  : {result.get('required_rewrites', [])}")
    print(f"   Final Status     : {result.get('final_status', '?').upper()}")

    if result.get("global_issues"):
        print("   Global Issues:")
        for issue in result["global_issues"]:
            print(f"     • {issue}")

    return result


def assemble_manuscript() -> str:
    """
    Assemble the final manuscript from all approved polished chapters.
    No rewriting. No inserted bridges unless continuity report explicitly approved them.
    Only combines chapter_polished_XX.md files in locked order.
    """
    chapters = _load_all_polished_chapters()

    # Check continuity report for any outstanding required rewrites
    continuity_path = OUTPUT_DIR / "continuity_report.json"
    if continuity_path.exists():
        with open(continuity_path) as f:
            continuity = json.load(f)
        if continuity.get("required_rewrites"):
            remaining = continuity["required_rewrites"]
            print(f"\n⛔ Assembly blocked — {len(remaining)} chapters need revision: {remaining}")
            print("   Run rewrite loop on flagged chapters before assembling.")
            return ""

    book_brief = {}
    brief_path = MEMORY_DIR / "book_brief.json"
    if brief_path.exists():
        with open(brief_path) as f:
            book_brief = json.load(f)

    # Build manuscript
    sections = [
        f"# {book_brief.get('working_title', 'Manuscript')}\n",
        f"### {book_brief.get('subtitle_options', [''])[0]}\n\n---\n\n" if book_brief.get("subtitle_options") else "",
    ]

    for num in sorted(chapters.keys()):
        sections.append(chapters[num])
        sections.append("\n\n---\n\n")

    manuscript = "\n".join(sections)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "manuscript_v1.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(manuscript)

    total_words = len(manuscript.split())
    print(f"\n📖 Manuscript Assembled")
    print(f"   Chapters : {len(chapters)}")
    print(f"   Words    : {total_words:,}")
    print(f"   Saved    : {output_path}")

    return manuscript
