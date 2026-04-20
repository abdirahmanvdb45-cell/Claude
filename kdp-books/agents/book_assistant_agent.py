"""
AGENT 7: Book Assistant
An interactive agent that answers questions about any completed manuscript.
After giving suggestions, it offers to apply them directly to the chapters.
"""

import anthropic
import os
import re
from config import ANTHROPIC_API_KEY, MANUSCRIPTS_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

ASSISTANT_SYSTEM = """You are a Book Assistant with full knowledge of the manuscript provided to you.

You can answer any question about the book, including:
- Chapter summaries, overall summary, key themes
- Strongest and weakest sections with specific reasons
- What the reader will feel after each chapter
- Suggested edits or improvements
- Marketing hooks or taglines drawn from the content

Be specific and reference the actual content. Quote directly when useful.
When you identify improvements, be clear and specific about WHICH chapter needs changing and WHAT exactly should change."""

APPLY_SYSTEM = """You are a professional book editor. You will be given:
1. A specific improvement suggestion
2. The original chapter text

Your job: apply the improvement and return the COMPLETE rewritten chapter.
- Preserve the author's voice and style
- Only change what the suggestion targets
- Return the full chapter text, ready to save — no commentary, no notes"""

DETECTION_SYSTEM = """You read an assistant's response and determine if it contains actionable improvement suggestions for a book.

Return ONLY valid JSON in this exact format:
{"has_suggestions": true or false, "chapters_affected": ["chapter_01_filename.md", ...], "summary": "one line describing the improvements"}

If no specific improvements are suggested, return: {"has_suggestions": false, "chapters_affected": [], "summary": ""}"""


def load_chapters(folder_name: str) -> dict[str, str]:
    """Returns dict of filename -> content for all chapters."""
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)
    chapters = {}
    for f in sorted(os.listdir(book_dir)):
        if f.startswith("chapter_") and f.endswith(".md") and "_edited" not in f:
            with open(os.path.join(book_dir, f), encoding="utf-8", errors="replace") as fh:
                chapters[f] = fh.read()
    return chapters


def load_manuscript(folder_name: str) -> str:
    """Loads full manuscript text."""
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)

    for f in os.listdir(book_dir):
        if f.startswith("FULL_MANUSCRIPT") and f.endswith(".md"):
            with open(os.path.join(book_dir, f), encoding="utf-8", errors="replace") as fh:
                return fh.read()

    chapters = load_chapters(folder_name)
    return "\n\n---\n\n".join(chapters.values())


def detect_suggestions(answer: str, chapter_filenames: list[str]) -> dict:
    """Asks Claude if the answer contains actionable suggestions."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=DETECTION_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Assistant response to analyse:
{answer}

Available chapter filenames:
{chr(10).join(chapter_filenames)}

Does this response contain specific improvement suggestions? Return JSON only."""
        }]
    )
    text = response.content[0].text.strip()
    # Extract JSON if wrapped in code block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        import json
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"has_suggestions": False, "chapters_affected": [], "summary": ""}


def apply_suggestion_to_chapter(chapter_content: str, suggestion: str, chapter_filename: str) -> str:
    """Rewrites a chapter applying the given suggestion."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=APPLY_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Improvement to apply:
{suggestion}

Original chapter ({chapter_filename}):
{chapter_content}

Return the complete rewritten chapter with the improvement applied."""
        }]
    )
    return response.content[0].text


def save_chapter(folder_name: str, filename: str, content: str):
    """Overwrites the chapter file with the improved version."""
    path = os.path.join(MANUSCRIPTS_DIR, folder_name, filename)
    # Back up original if not already backed up
    backup_path = path.replace(".md", "_original.md")
    if not os.path.exists(backup_path):
        with open(path, encoding="utf-8", errors="replace") as f:
            original = f.read()
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(original)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def run_book_assistant():
    folders = [f for f in os.listdir(MANUSCRIPTS_DIR)
               if os.path.isdir(os.path.join(MANUSCRIPTS_DIR, f)) and not f.startswith('.')]

    if not folders:
        print("No manuscripts found.")
        return

    print("\nAvailable manuscripts:")
    for i, folder in enumerate(folders, 1):
        chapter_count = len([f for f in os.listdir(os.path.join(MANUSCRIPTS_DIR, folder))
                             if f.startswith("chapter_") and f.endswith(".md") and "_edited" not in f and "_original" not in f])
        print(f"  {i}. {folder.replace('_', ' ').title()}  ({chapter_count} chapters)")

    pick = input("\nWhich book? (number): ").strip()
    try:
        folder_name = folders[int(pick) - 1]
    except (IndexError, ValueError):
        print("Invalid selection.")
        return

    book_title = folder_name.replace("_", " ").title()
    print(f"\nLoading: {book_title}...")
    manuscript = load_manuscript(folder_name)
    chapters = load_chapters(folder_name)
    chapter_filenames = list(chapters.keys())

    if not manuscript:
        print("No content found.")
        return

    print(f"Loaded. ({len(manuscript):,} characters, {len(chapters)} chapters)")
    print(f"\nBook Assistant ready for: {book_title}")
    print("Ask anything. Type 'exit' to quit.\n")

    # Truncate for context
    manuscript_ctx = manuscript[:150_000] + "\n\n[...truncated...]" if len(manuscript) > 150_000 else manuscript
    conversation = []

    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit", "q"):
            print("Exiting Book Assistant.")
            break
        if not question:
            continue

        # Build message with manuscript on first turn, just question on subsequent turns
        if not conversation:
            user_content = f"""Here is the full manuscript for "{book_title}":

---MANUSCRIPT START---
{manuscript_ctx}
---MANUSCRIPT END---

{question}"""
        else:
            user_content = question

        conversation.append({"role": "user", "content": user_content})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=ASSISTANT_SYSTEM,
            messages=conversation,
        )

        answer = response.content[0].text
        conversation.append({"role": "assistant", "content": answer})

        print(f"\nAssistant: {answer}\n")

        # Check if the answer contains actionable suggestions
        detection = detect_suggestions(answer, chapter_filenames)
        if detection.get("has_suggestions"):
            affected = detection.get("chapters_affected", [])
            summary = detection.get("summary", "improvements identified")
            print(f"  → Improvements detected: {summary}")
            if affected:
                print(f"  → Chapters to update: {', '.join(affected)}")
            apply = input("  Apply these improvements now? (y/n): ").strip().lower()
            if apply == "y":
                targets = affected if affected else chapter_filenames
                for filename in targets:
                    if filename in chapters:
                        print(f"  → Applying to {filename}...")
                        improved = apply_suggestion_to_chapter(chapters[filename], answer, filename)
                        save_chapter(folder_name, filename, improved)
                        chapters[filename] = improved  # update in memory
                        print(f"     ✓ Saved (original backed up as {filename.replace('.md', '_original.md')})")
                print("\n  ✓ All improvements applied. Ask another question or type 'exit'.\n")


if __name__ == "__main__":
    print("=" * 50)
    print("   BOOK ASSISTANT")
    print("=" * 50)
    run_book_assistant()
