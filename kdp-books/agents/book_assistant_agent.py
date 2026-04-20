"""
AGENT 7: Book Assistant
An interactive agent that answers questions about any completed manuscript.
Ask anything: chapter summaries, themes, character arcs, word counts, etc.

Run standalone: python book_assistant_agent.py
Or accessed via option 5 in automation_agent.py
"""

import anthropic
import json
import os
from config import ANTHROPIC_API_KEY, MANUSCRIPTS_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a Book Assistant with full knowledge of the manuscript provided to you.

You can answer any question about the book, including:
- Chapter summaries (e.g. "Summarise chapter 4")
- Overall book summary
- Key themes and arguments
- Character descriptions and arcs (for fiction)
- Word count estimates
- What the book promises the reader
- How chapters connect to each other
- Strongest and weakest sections
- What a reader will feel after each chapter
- Suggested edits or improvements
- Marketing hooks or taglines drawn from the content

Be specific and reference the actual content. Quote directly when useful.
Keep answers clear and useful. If asked for a summary, be concise but complete."""


def load_manuscript(folder_name: str) -> tuple[str, str]:
    """Loads the full compiled manuscript or assembles from chapters."""
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)

    # Try compiled first
    for f in os.listdir(book_dir):
        if f.startswith("FULL_MANUSCRIPT") and f.endswith(".md"):
            with open(os.path.join(book_dir, f), encoding="utf-8", errors="replace") as fh:
                return f, fh.read()

    # Fall back to assembling chapters
    chapter_files = sorted([f for f in os.listdir(book_dir)
                            if f.startswith("chapter_") and f.endswith(".md")])
    if not chapter_files:
        return "", ""

    content = ""
    for cf in chapter_files:
        with open(os.path.join(book_dir, cf), encoding="utf-8", errors="replace") as fh:
            content += fh.read() + "\n\n---\n\n"

    return f"{len(chapter_files)} chapters", content


def ask_about_book(manuscript_content: str, book_title: str, question: str) -> str:
    """Sends a question about the manuscript to Claude and returns the answer."""
    # Truncate if manuscript is very long (keep within context limits)
    max_chars = 150_000
    if len(manuscript_content) > max_chars:
        manuscript_content = manuscript_content[:max_chars] + "\n\n[...manuscript truncated for context...]"

    messages = [
        {
            "role": "user",
            "content": f"""Here is the full manuscript for "{book_title}":

---MANUSCRIPT START---
{manuscript_content}
---MANUSCRIPT END---

Question: {question}"""
        }
    ]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text


def run_book_assistant():
    """Interactive loop for asking questions about a book."""
    # List available manuscripts
    folders = [f for f in os.listdir(MANUSCRIPTS_DIR)
               if os.path.isdir(os.path.join(MANUSCRIPTS_DIR, f)) and not f.startswith('.')]

    if not folders:
        print("No manuscripts found in the manuscripts folder.")
        return

    print("\nAvailable manuscripts:")
    for i, folder in enumerate(folders, 1):
        chapter_count = len([f for f in os.listdir(os.path.join(MANUSCRIPTS_DIR, folder))
                             if f.startswith("chapter_") and f.endswith(".md")])
        print(f"  {i}. {folder.replace('_', ' ').title()}  ({chapter_count} chapters)")

    pick = input("\nWhich book? (number): ").strip()
    try:
        folder_name = folders[int(pick) - 1]
    except (IndexError, ValueError):
        print("Invalid selection.")
        return

    book_title = folder_name.replace("_", " ").title()
    print(f"\nLoading: {book_title}...")
    source, manuscript = load_manuscript(folder_name)

    if not manuscript:
        print("No content found in this manuscript folder.")
        return

    print(f"Loaded. ({len(manuscript):,} characters)")
    print(f"\nBook Assistant ready for: {book_title}")
    print("Ask anything. Type 'exit' to quit.\n")
    print("Examples:")
    print("  - Give me a summary of chapter 3")
    print("  - What are the main themes of this book?")
    print("  - Write a back-cover blurb for this book")
    print("  - What does the reader feel by the end?")
    print("  - What is the weakest chapter and why?\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit", "q"):
            print("Exiting Book Assistant.")
            break
        if not question:
            continue

        print("\nAssistant: ", end="", flush=True)
        answer = ask_about_book(manuscript, book_title, question)
        print(answer)
        print()


if __name__ == "__main__":
    print("=" * 50)
    print("   BOOK ASSISTANT")
    print("=" * 50)
    run_book_assistant()
