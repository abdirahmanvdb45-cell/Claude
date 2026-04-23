"""
Input Normalizer Agent — V3 Core Pipeline
Converts raw user project requests into clean, standardised internal briefs.
Flags ambiguity, missing information, and hidden risks before any planning starts.

Instead of pausing and exiting, this agent asks clarifying questions interactively
in the terminal and folds the answers into the normalized input before proceeding.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()

MEMORY_DIR  = Path(__file__).parent / "memory"
INPUT_FILE  = Path(__file__).parent / "input" / "project_request.json"

# Questions to ask if specific fields are missing or vague
CLARIFYING_QUESTIONS = [
    {
        "key":      "unique_angle",
        "label":    "Unique angle",
        "question": "What makes this book different from books like Models (Manson) or No More Mr Nice Guy?\n  (Your personal take, your experience, what you've figured out that others miss)",
    },
    {
        "key":      "author_background",
        "label":    "Author background",
        "question": "What's your personal background or experience that gives you the right to write this?\n  (Lived experience counts — no formal credentials needed)",
    },
    {
        "key":      "scope",
        "label":    "Scope",
        "question": "Is this book mainly about early dating / attraction, long-term relationships, or both?",
    },
    {
        "key":      "structure",
        "label":    "Structure",
        "question": "How do you want the book structured?\n  [1] One trait or theme per chapter (e.g. Presence, Decisiveness, etc.)\n  [2] Problem / Solution (here's what's going wrong, here's the fix)\n  [3] A journey from first impression to long-term relationship\n  Enter 1, 2, or 3 (or describe your preference):",
    },
    {
        "key":      "includes_case_studies",
        "label":    "Examples",
        "question": "Do you want real-life scenarios and examples woven into the chapters? [y/n]",
    },
    {
        "key":      "spelling_convention",
        "label":    "Spelling",
        "question": "British English or American English? [b/a]",
    },
]

STRUCTURE_MAP = {
    "1": "Trait and behavior-based — one core theme per chapter",
    "2": "Problem / Solution — each chapter identifies a common pattern and gives the fix",
    "3": "Chronological journey from first impression through to long-term relationship",
}

SPELLING_MAP = {
    "b": "British English",
    "a": "American English",
}


def ask_missing_questions(project_request: dict) -> dict:
    """
    Ask the user interactively in the terminal for any missing or vague fields.
    Updates project_request in place and saves back to input/project_request.json.
    Returns the enriched project_request.
    """
    enriched = dict(project_request)
    asked_any = False

    for q in CLARIFYING_QUESTIONS:
        key = q["key"]
        # Skip if already filled in with a real value
        existing = enriched.get(key)
        if existing and str(existing).strip() and existing not in ("", "unknown", "tbd"):
            continue

        if not asked_any:
            print("\n" + "="*60)
            print("❓ A few quick questions to help write a better book")
            print("   (Press Enter to skip any question)")
            print("="*60)
            asked_any = True

        print(f"\n  {q['label']}:")
        print(f"  {q['question']}")
        answer = input("  → ").strip()

        if not answer:
            continue

        # Map shorthand answers
        if key == "structure":
            answer = STRUCTURE_MAP.get(answer, answer)
        elif key == "spelling_convention":
            answer = SPELLING_MAP.get(answer.lower(), "British English")
        elif key == "includes_case_studies":
            answer = answer.lower() in ("y", "yes", "1", "true")

        enriched[key] = answer

    if asked_any:
        # Save enriched request back to disk so --resume picks it up
        INPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(enriched, f, indent=2, ensure_ascii=False)
        print("\n  ✅ Answers saved — continuing pipeline...\n")

    return enriched


def normalize_input(project_request: dict) -> dict:
    """
    Normalize a raw project request into a clean publishing input object.
    Asks the user interactively for any missing fields instead of pausing.

    Args:
        project_request: Raw dict from input/project_request.json

    Returns:
        Normalized dict saved to memory/normalized_input.json
    """
    # ── Step 1: fill gaps interactively ──────────────────────────
    project_request = ask_missing_questions(project_request)

    # ── Step 2: Claude normalizes the enriched request ───────────
    system_prompt = """You are the Input Normalizer. Your job is to take a project request
and convert it into clean, precise publishing instructions. You do not invent facts.
You flag every remaining ambiguity explicitly. Output valid JSON only — no markdown fences."""

    user_prompt = f"""Normalize this project request into a clean publishing input.

RAW PROJECT REQUEST:
{json.dumps(project_request, indent=2)}

Rules:
- do not invent missing facts
- flag only genuinely blocking ambiguities — minor gaps are NOT blocking
- standardize reader, tone, and objective language
- identify scope risks (too broad, too narrow, too vague)
- identify evidence risks (claims that need research support)
- list what you are ALLOWED to assume
- list what you must NOT assume
- gate_status should be "proceed" unless something is genuinely unworkable

Return this exact JSON (no markdown, no fences):
{{
  "project_type": "nonfiction",
  "topic_normalized": "<clean topic statement>",
  "reader_normalized": "<precise reader description>",
  "desired_outcome": "<what the reader achieves after reading>",
  "tone_normalized": ["<tone 1>", "<tone 2>"],
  "length_classification": "<short_form|standard|long_form>",
  "scope_risks": ["<risk>", ...],
  "missing_information": ["<item>", ...],
  "assumptions_allowed": ["<assumption>", ...],
  "assumptions_forbidden": ["<assumption>", ...],
  "evidence_risks": ["<risk>", ...],
  "gate_status": "<proceed|pause_for_human_input>",
  "gate_reason": "<why paused or why proceeding>"
}}

Gate rules:
- If reader is completely unknown → pause_for_human_input
- If goal is totally undefined → pause_for_human_input
- If source material is missing → proceed but add evidence risk flag
- Everything else → proceed"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()

    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    # Carry forward enriched fields so downstream agents can use them
    for field in ("unique_angle", "author_background", "scope", "structure",
                  "includes_case_studies", "spelling_convention", "author_name",
                  "book_title"):
        if project_request.get(field):
            result[field] = project_request[field]

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    output_path = MEMORY_DIR / "normalized_input.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n📋 Input Normalizer")
    print(f"   Topic     : {result.get('topic_normalized', '')[:80]}")
    print(f"   Reader    : {result.get('reader_normalized', '')[:80]}")
    print(f"   Gate      : {result.get('gate_status', '').upper()}")

    if result.get("missing_information"):
        blocking = [m for m in result["missing_information"] if m]
        if blocking:
            print("   Notes:")
            for m in blocking[:5]:
                print(f"     • {m}")

    return result
