"""
AGENT 9: Rewrite Agent
Takes any existing manuscript and rewrites it completely based on
a user instruction — different style, stronger voice, new angle,
higher quality, or a full genre shift.

Accessed via option 7 in automation_agent.py
"""

import anthropic
import os
import re
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MANUSCRIPTS_DIR, PUBLISH_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

REWRITE_SYSTEM = """You are a master ghostwriter who can rewrite any book chapter
to a new specification while preserving the core ideas and information.

Your rewrite principles:
1. KEEP THE IDEAS — preserve the core argument, examples, and information
2. TRANSFORM THE EXECUTION — change the style, voice, structure as instructed
3. NO PLACEHOLDERS — write every word of the full chapter
4. MATCH THE TARGET — if told to write like a specific style, commit to it fully
5. IMPROVE ON THE ORIGINAL — the rewrite should be better, not just different"""


def _slugify(text: str, max_len: int = 40) -> str:
    slug = text.lower()
    slug = re.sub(r'[<>:"/\\|?*,\'!]', '', slug)
    slug = re.sub(r'\s+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug[:max_len]


def load_chapters(folder_name: str) -> list[dict]:
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)
    chapters = []
    for f in sorted(os.listdir(book_dir)):
        if f.startswith("chapter_") and f.endswith(".md") and "_rewrite" not in f and "_original" not in f and "_edited" not in f:
            path = os.path.join(book_dir, f)
            with open(path, encoding="utf-8", errors="replace") as fh:
                chapters.append({"filename": f, "content": fh.read(), "path": path})
    return chapters


def rewrite_chapter(original: str, filename: str, instruction: str,
                    book_title: str, chapter_num: int, total: int) -> str:
    """Rewrites a single chapter according to the instruction."""
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8000,
        system=REWRITE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"""Rewrite instruction: {instruction}

Book: {book_title}
Chapter {chapter_num} of {total}: {filename}

ORIGINAL CHAPTER:
{original}

Rewrite the COMPLETE chapter according to the instruction above.
Same core ideas and information — transformed execution.
Return only the rewritten chapter text, no commentary."""
        }]
    )
    return response.content[0].text


def save_rewritten_chapter(original_path: str, content: str, rewrite_label: str) -> str:
    """Saves the rewritten chapter alongside the original."""
    # Back up original if not already done
    backup = original_path.replace(".md", "_original.md")
    if not os.path.exists(backup):
        with open(original_path, encoding="utf-8", errors="replace") as f:
            orig = f.read()
        with open(backup, "w", encoding="utf-8") as f:
            f.write(orig)

    label = _slugify(rewrite_label, 20)
    rewrite_path = original_path.replace(".md", f"_rewrite_{label}.md")
    with open(rewrite_path, "w", encoding="utf-8") as f:
        f.write(content)
    return rewrite_path


def compile_rewrite(folder_name: str, book_title: str, rewrite_label: str) -> str:
    """Compiles rewritten chapters into a full manuscript and exports to Word."""
    book_dir = os.path.join(MANUSCRIPTS_DIR, folder_name)
    label = _slugify(rewrite_label, 20)
    slug = _slugify(book_title)
    output_path = os.path.join(book_dir, f"REWRITE_{label}_{slug}.md")

    chapter_files = sorted(os.listdir(book_dir))

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"# {book_title}\n*Rewrite: {rewrite_label}*\n\n---\n\n")
        for cf in chapter_files:
            if f"_rewrite_{label}" in cf and cf.endswith(".md"):
                with open(os.path.join(book_dir, cf), encoding="utf-8", errors="replace") as ch:
                    out.write(ch.read())
                    out.write("\n\n---\n\n")

    # Export to Word
    word_path = _export_word(book_title, rewrite_label, output_path)
    return output_path, word_path


def _export_word(book_title: str, rewrite_label: str, manuscript_path: str) -> str:
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return "python-docx not installed"

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    tp = doc.add_paragraph()
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = tp.add_run(book_title.upper())
    r.bold = True
    r.font.size = Pt(28)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"Rewrite: {rewrite_label}").italic = True
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
            pattern = re.compile(r'(\*\*.*?\*\*|\*.*?\*)')
            for part in pattern.split(line.strip()):
                if part.startswith("**") and part.endswith("**"):
                    para.add_run(part[2:-2]).bold = True
                elif part.startswith("*") and part.endswith("*"):
                    para.add_run(part[1:-1]).italic = True
                else:
                    para.add_run(part)

    safe_title = re.sub(r'[<>:"/\\|?*]', '', book_title).strip()
    safe_label = re.sub(r'[<>:"/\\|?*]', '', rewrite_label).strip()
    word_path = os.path.join(PUBLISH_DIR, f"{safe_title} — {safe_label}.docx")
    doc.save(word_path)
    return word_path


def run_rewrite_agent():
    folders = [f for f in os.listdir(MANUSCRIPTS_DIR)
               if os.path.isdir(os.path.join(MANUSCRIPTS_DIR, f)) and not f.startswith('.')]

    if not folders:
        print("No manuscripts found.")
        return

    print("\nAvailable manuscripts:")
    for i, folder in enumerate(folders, 1):
        count = len([f for f in os.listdir(os.path.join(MANUSCRIPTS_DIR, folder))
                     if f.startswith("chapter_") and f.endswith(".md")
                     and "_rewrite" not in f and "_original" not in f and "_edited" not in f])
        print(f"  {i}. {folder.replace('_', ' ').title()}  ({count} chapters)")

    pick = input("\nWhich book to rewrite? (number): ").strip()
    try:
        folder_name = folders[int(pick) - 1]
    except (IndexError, ValueError):
        print("Invalid selection.")
        return

    book_title = folder_name.replace("_", " ").title()

    print(f"\nBook: {book_title}")
    print("\nRewrite examples:")
    print("  - Make it more conversational and warm, less academic")
    print("  - Rewrite in the style of James Clear (Atomic Habits)")
    print("  - Make it shorter and punchier — cut every chapter by 30%")
    print("  - Rewrite for a female audience instead of male")
    print("  - Make the tone more urgent and direct")
    print("  - Add more storytelling — every section should open with a story")
    print()

    instruction = input("Rewrite instruction: ").strip()
    if not instruction:
        print("No instruction given.")
        return

    rewrite_label = input("Name this version (e.g. 'punchy', 'james-clear-style'): ").strip() or "rewrite"

    chapters = load_chapters(folder_name)
    if not chapters:
        print("No chapters found.")
        return

    print(f"\nRewriting {len(chapters)} chapters...")
    print(f"Instruction: {instruction}\n")

    for i, ch in enumerate(chapters, 1):
        print(f"  → Chapter {i}/{len(chapters)}: {ch['filename']}...")
        rewritten = rewrite_chapter(
            ch["content"], ch["filename"], instruction,
            book_title, i, len(chapters)
        )
        save_rewritten_chapter(ch["path"], rewritten, rewrite_label)
        print(f"     ✓ Done")

    print("\n  → Compiling rewritten manuscript...")
    md_path, word_path = compile_rewrite(folder_name, book_title, rewrite_label)
    print(f"\n  ✓ Word file: {word_path}")
    print(f"  ✓ Originals backed up as *_original.md in the manuscript folder")
    print("\nRewrite complete.")


if __name__ == "__main__":
    print("=" * 50)
    print("   REWRITE AGENT")
    print("=" * 50)
    run_rewrite_agent()
