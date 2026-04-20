"""
AGENT 8: Editing Agent
Reads a completed manuscript, identifies structural and line-level issues,
rewrites weak sections, removes redundancy, and saves a polished final draft
ready for publishing.

Run standalone: python editing_agent.py
Or accessed via option 6 in automation_agent.py
"""

import anthropic
import json
import os
import re
from datetime import datetime
from config import ANTHROPIC_API_KEY, MANUSCRIPTS_DIR, PUBLISH_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

EDITOR_SYSTEM = """You are a professional book editor with 20+ years of experience editing
bestselling non-fiction and fiction. You combine the instincts of a developmental editor,
line editor, and copy editor.

Your editing principles:
1. PROTECT THE AUTHOR'S VOICE — improve clarity and flow without changing the style
2. CUT RUTHLESSLY — every sentence must earn its place; remove repetition and filler
3. FIX STRUCTURE — if chapters overlap or repeat, consolidate them
4. STRENGTHEN OPENINGS — every chapter must hook in the first paragraph
5. IMPROVE TRANSITIONS — chapters should flow into each other naturally
6. CONSISTENCY — names, metaphors, and arguments must be consistent throughout
7. READER FIRST — at every decision ask: does this serve the reader?

When you edit a chapter, return the FULL rewritten chapter text — not notes or suggestions.
The output should be publication-ready prose."""

DIAGNOSTIC_SYSTEM = """You are a structural editor assessing a complete manuscript.
Identify every problem clearly and specifically. Be honest and direct.
Your job is to produce a diagnosis that guides the editing pass."""


def load_chapters(folder_name: str) -> list[dict]:
    """Loads all chapters as a list of dicts with filename and content."""
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)
    chapter_files = sorted([f for f in os.listdir(book_dir)
                            if f.startswith("chapter_") and f.endswith(".md")])
    chapters = []
    for cf in chapter_files:
        with open(os.path.join(book_dir, cf), encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        chapters.append({"filename": cf, "content": content, "path": os.path.join(book_dir, cf)})
    return chapters


def diagnose_manuscript(chapters: list[dict], book_title: str) -> str:
    """Asks Claude to do a full structural diagnosis of the manuscript."""
    print("  → Running structural diagnosis...")

    # Build a chapter list with first 200 chars of each for context
    chapter_overview = ""
    for i, ch in enumerate(chapters, 1):
        preview = ch["content"][:300].replace("\n", " ")
        chapter_overview += f"\nChapter {i} ({ch['filename']}):\n{preview}...\n"

    # For full diagnosis, send entire manuscript (chunked if needed)
    full_text = "\n\n---\n\n".join(ch["content"] for ch in chapters)
    if len(full_text) > 120_000:
        full_text = full_text[:120_000] + "\n\n[...truncated...]"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=DIAGNOSTIC_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Diagnose this manuscript: "{book_title}"

{full_text}

Provide a structured diagnosis covering:
1. STRUCTURAL ISSUES — chapters that repeat content, wrong order, missing sections
2. REDUNDANCY — metaphors, examples, or arguments that appear more than once
3. WEAK CHAPTERS — which chapters underperform and why (be specific)
4. STRONG CHAPTERS — which chapters are working well
5. OPENING PROBLEMS — chapters that start weakly
6. VOICE INCONSISTENCIES — places where the tone shifts unexpectedly
7. PRIORITY EDIT LIST — the 5 most important fixes, in order

Be specific: name the chapter, quote the problem, explain the fix."""
        }]
    )
    return response.content[0].text


def edit_chapter(chapter_content: str, book_title: str, chapter_filename: str,
                 diagnosis: str, all_chapter_titles: list[str]) -> str:
    """Rewrites a single chapter based on the diagnosis."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=EDITOR_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Edit this chapter from "{book_title}".

MANUSCRIPT DIAGNOSIS (for context):
{diagnosis[:2000]}

ALL CHAPTERS IN BOOK (for context on what NOT to repeat):
{chr(10).join(all_chapter_titles)}

CHAPTER TO EDIT ({chapter_filename}):
{chapter_content}

Rewrite this chapter with these priorities:
1. Remove any content that repeats what other chapters already cover
2. Strengthen the opening — hook the reader in the first paragraph
3. Improve clarity and flow at the sentence level
4. Cut filler — every paragraph must earn its place
5. Ensure the chapter ends with either a clear takeaway or a hook to the next chapter
6. Preserve the author's voice and style

Return the COMPLETE rewritten chapter — full text, ready to publish."""
        }]
    )
    return response.content[0].text


def save_edited_chapter(original_path: str, edited_content: str) -> str:
    """Saves the edited chapter back to the manuscript folder."""
    dir_name = os.path.dirname(original_path)
    base_name = os.path.basename(original_path)
    edited_filename = base_name.replace(".md", "_edited.md")
    edited_path = os.path.join(dir_name, edited_filename)
    with open(edited_path, "w", encoding="utf-8") as f:
        f.write(edited_content)
    return edited_path


def compile_edited_manuscript(folder_name: str, book_title: str) -> str:
    """Compiles edited chapters into a final manuscript. Falls back to originals if no edit exists."""
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)
    chapter_files = sorted([f for f in os.listdir(book_dir)
                            if f.startswith("chapter_") and f.endswith(".md")
                            and "_edited" not in f])

    slug = re.sub(r'[<>:"/\\|?*,\'!]', '', book_title.lower())
    slug = re.sub(r'\s+', '_', slug)[:40]
    output_path = os.path.join(book_dir, f"FINAL_EDITED_{slug}.md")

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"# {book_title}\n\n---\n\n")
        for cf in chapter_files:
            edited = cf.replace(".md", "_edited.md")
            edited_path = os.path.join(book_dir, edited)
            source_path = os.path.join(book_dir, cf)
            use_path = edited_path if os.path.exists(edited_path) else source_path
            with open(use_path, encoding="utf-8", errors="replace") as ch:
                out.write(ch.read())
                out.write("\n\n---\n\n")

    return output_path


def export_final_word(book_title: str, manuscript_path: str) -> str:
    """Exports the final edited manuscript to a Word file in the publish folder."""
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import re as _re
    except ImportError:
        return "python-docx not installed"

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run(book_title.upper())
    run.bold = True
    run.font.size = Pt(28)
    doc.add_paragraph()

    with open(manuscript_path, encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip("\n")
        if line.startswith("# "):
            text = line[2:].strip()
            if text.upper() == book_title.upper():
                continue
            h = doc.add_heading(text, level=1)
            if h.runs:
                h.runs[0].font.size = Pt(20)
        elif line.startswith("## "):
            h = doc.add_heading(line[3:].strip(), level=2)
            if h.runs:
                h.runs[0].font.size = Pt(14)
        elif line.strip() == "---":
            doc.add_paragraph("─" * 40).alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif line.strip() == "":
            doc.add_paragraph()
        else:
            para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(6)
            pattern = _re.compile(r'(\*\*.*?\*\*|\*.*?\*)')
            parts = pattern.split(line.strip())
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    r = para.add_run(part[2:-2])
                    r.bold = True
                elif part.startswith("*") and part.endswith("*"):
                    r = para.add_run(part[1:-1])
                    r.italic = True
                else:
                    para.add_run(part)

    safe_title = re.sub(r'[<>:"/\\|?*]', '', book_title).strip()
    word_path = os.path.join(PUBLISH_DIR, f"{safe_title} — Final Edit.docx")
    doc.save(word_path)
    return word_path


def run_editing_agent():
    """Main editing pipeline: diagnose → edit each chapter → compile → export Word."""
    folders = [f for f in os.listdir(MANUSCRIPTS_DIR)
               if os.path.isdir(os.path.join(MANUSCRIPTS_DIR, f)) and not f.startswith('.')]

    if not folders:
        print("No manuscripts found.")
        return

    print("\nAvailable manuscripts:")
    for i, folder in enumerate(folders, 1):
        chapter_count = len([f for f in os.listdir(os.path.join(MANUSCRIPTS_DIR, folder))
                             if f.startswith("chapter_") and f.endswith(".md")
                             and "_edited" not in f])
        print(f"  {i}. {folder.replace('_', ' ').title()}  ({chapter_count} chapters)")

    pick = input("\nWhich book to edit? (number): ").strip()
    try:
        folder_name = folders[int(pick) - 1]
    except (IndexError, ValueError):
        print("Invalid selection.")
        return

    book_title = folder_name.replace("_", " ").title()
    print(f"\nEditing: {book_title}")

    chapters = load_chapters(folder_name)
    if not chapters:
        print("No chapters found.")
        return

    print(f"Loaded {len(chapters)} chapters.\n")

    # Step 1: Diagnose
    diagnosis = diagnose_manuscript(chapters, book_title)
    print("\n--- DIAGNOSIS ---")
    print(diagnosis)
    print("-" * 40)

    proceed = input("\nProceed with editing all chapters? (y/n): ").strip().lower()
    if proceed != "y":
        print("Editing cancelled.")
        return

    # Step 2: Edit each chapter
    all_titles = [ch["filename"] for ch in chapters]
    for i, chapter in enumerate(chapters, 1):
        print(f"  → Editing chapter {i}/{len(chapters)}: {chapter['filename']}...")
        edited = edit_chapter(chapter["content"], book_title, chapter["filename"],
                              diagnosis, all_titles)
        save_edited_chapter(chapter["path"], edited)
        print(f"     ✓ Saved")

    # Step 3: Compile final manuscript
    print("\n  → Compiling final edited manuscript...")
    final_md_path = compile_edited_manuscript(folder_name, book_title)
    print(f"  ✓ Compiled: {final_md_path}")

    # Step 4: Export to Word
    print("  → Exporting to Word...")
    word_path = export_final_word(book_title, final_md_path)
    print(f"\n  ✓ Final Word file: {word_path}")
    print("\nEditing complete. Your book is ready to publish.")


if __name__ == "__main__":
    print("=" * 50)
    print("   EDITING AGENT")
    print("=" * 50)
    run_editing_agent()
