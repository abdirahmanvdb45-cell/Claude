"""
AGENT 4: Book Writing Agent (Upgraded)
Writes full books with:
- Character Bible (consistent names, traits across chapters)
- Chapter Summaries (each chapter knows what came before)
- Continuity Checker (catches contradictions before compile)
- Style Guide (voice stays consistent throughout)
- Chapter Quality Check (auto-extends short chapters)
- Front/Back Matter Generator (preface, TOC, about author, etc.)

Strategies sourced from:
- sopher.ai (github.com/cheesejaguar/sopher.ai) — context management, continuity
- wesleyscholl/book-generator — quality checks, front/back matter, EPUB export
"""

import anthropic
import json
import os
import re
from datetime import datetime
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MANUSCRIPTS_DIR, PUBLISH_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MIN_CHAPTER_WORDS = 2500  # Auto-extend if below this

SYSTEM_PROMPT = """You are a professional ghostwriter and bestselling author with expertise in:
- Non-fiction: self-help, personal development, business, health, finance
- Fiction: romance, thriller, cozy fantasy, psychological suspense
- Amazon KDP formatting requirements and reader expectations
- Writing styles that generate 5-star reviews

Your writing principles:
1. CONVERSATIONAL AUTHORITY — write like a knowledgeable friend, not a professor
2. STORY FIRST — even non-fiction leads with stories before frameworks
3. SPECIFICITY OVER GENERALITY — real examples, real numbers, real scenarios
4. TRANSFORMATION ARC — every chapter moves the reader from where they are to where they want to be
5. PATTERN INTERRUPTS — vary sentence length, use direct questions, break up text with lists
6. READER VOICE — write sentences readers will highlight and screenshot
7. NO FLUFF — every paragraph earns its place; cut anything that doesn't serve the reader
8. NEVER REPEAT — check the chapter summaries provided and never re-explain what was already covered

Non-fiction structure (default):
- Hook chapter (promise + proof + path)
- Problem diagnosis (name their pain precisely)
- Mindset shift (challenge their current belief)
- Framework chapters (the system/method)
- Application chapters (how to actually do it)
- Maintenance/next-level chapter
- Conclusion (vision of transformed self)

Fiction structure:
- Genre conventions always respected
- Pacing: establish setting + character → inciting incident → escalation → dark night → climax → resolution
- Every chapter ends with a micro-hook that compels the next chapter

KDP formatting requirements:
- 12pt font (Times New Roman or similar serif for print)
- Chapter headings: H1, section breaks: H2
- Front matter: title page, copyright, table of contents, dedication
- Back matter: about the author, review request, resources
- Non-fiction: 30,000–70,000 words ideal range
- Fiction: 60,000–100,000 words"""

CONTINUITY_SYSTEM = """You are a meticulous continuity editor. Read all provided chapters and identify inconsistencies.

Check for:
1. CHARACTER CONSISTENCY — names spelled differently, ages/descriptions that contradict
2. TIMELINE — events out of order, time spans that don't add up
3. FACTUAL CONSISTENCY — numbers, statistics, claims that contradict each other
4. REPEATED CONTENT — concepts explained more than twice, metaphors reused
5. TONE SHIFTS — sections that sound like a different author

Return a JSON object:
{
  "score": 0.0-1.0,
  "issues": [
    {"severity": "critical|major|minor", "location": "chapter X", "problem": "...", "fix": "..."}
  ],
  "repeated_phrases": ["phrase1", "phrase2"],
  "character_inconsistencies": ["..."],
  "recommendation": "one sentence summary"
}"""


def _slugify(text: str, max_len: int = 40) -> str:
    slug = text.lower()
    slug = re.sub(r'[<>:"/\\|?*,\'!]', '', slug)
    slug = re.sub(r'\s+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug[:max_len]


def _word_count(text: str) -> int:
    return len(text.split())


# ── Bible & Style Guide ──────────────────────────────────────────────────────

def build_character_bible(concept: dict, outline: dict) -> str:
    """Creates a character/entity bible from the concept and outline. Kept in memory during writing."""
    genre = concept.get("genre", "Non-fiction")
    is_fiction = any(g in genre.lower() for g in ["fiction", "romance", "thriller", "fantasy", "mystery"])

    if is_fiction:
        prompt = f"""Create a CHARACTER BIBLE for this book:
Title: {concept.get('working_title')}
Genre: {genre}
Outline: {json.dumps(outline.get('chapters', [])[:5], indent=2)}

Include for each main character:
- Full name (and any nicknames — pick ONE spelling and stick to it)
- Age, physical description (2-3 specific details)
- Personality in 3 words
- Role in the story
- Key relationships

Format as a reference card the writer checks before each chapter."""
    else:
        prompt = f"""Create a CONCEPT BIBLE for this non-fiction book:
Title: {concept.get('working_title')}
Genre: {genre}
Transformation Promise: {concept.get('transformation_promise', '')}
Outline: {json.dumps(outline.get('chapters', [])[:5], indent=2)}

List:
- The 1-2 recurring case study characters (name, backstory, situation — ONE consistent version)
- Core metaphors (e.g. "fire and spark") — list them so they aren't accidentally repeated
- Key terms with their exact definitions (pick one definition per term)
- What the book promises the reader (so every chapter serves it)"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def build_style_guide(concept: dict) -> str:
    """Creates a style guide that keeps voice consistent across all chapters."""
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": f"""Create a STYLE GUIDE for this book:
Title: {concept.get('working_title')}
Genre: {concept.get('genre', 'Non-fiction')}
Target Reader: {concept.get('target_reader_identity', 'General adult')}
Tone/Emotion: {concept.get('primary_emotion', 'aspiration')}

Define:
- Voice (e.g. "warm but direct, like a knowledgeable friend")
- Sentence style (e.g. "short paragraphs, punchy sentences, occasional longer reflective ones")
- What to avoid (e.g. "no jargon, no academic language, no victim-blaming")
- POV (second person 'you', first person 'I', or third person)
- Paragraph length (e.g. "rarely more than 4 sentences")
- Chapter opening style (e.g. "always open with a specific story or scenario")
- Chapter closing style (e.g. "end with a question or a bold statement")

Keep it to one short paragraph per rule."""}]
    )
    return response.content[0].text


def summarise_chapter(chapter_text: str, chapter_number: int) -> str:
    """Generates a short summary of a written chapter to pass to subsequent chapters."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": f"""Summarise Chapter {chapter_number} in 3-5 sentences.
Include: the main idea covered, any case study characters introduced or developed,
key metaphors or concepts introduced, and what the reader has been left with.

Chapter:
{chapter_text[:4000]}"""}]
    )
    return response.content[0].text


def extend_chapter(chapter_text: str, chapter_title: str, target_words: int, style_guide: str) -> str:
    """Extends a chapter that is below the minimum word count."""
    current = _word_count(chapter_text)
    needed = target_words - current
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": f"""This chapter is {current} words and needs {needed} more words.

STYLE GUIDE:
{style_guide}

CHAPTER SO FAR:
{chapter_text}

Extend it by adding:
- A deeper example or case study
- A practical exercise or reflection question for the reader
- Additional nuance on the main argument
- A stronger closing

Return the COMPLETE extended chapter — not just the addition."""}]
    )
    return response.content[0].text


# ── Front / Back Matter ──────────────────────────────────────────────────────

def generate_front_matter(book_title: str, concept: dict, outline: dict) -> str:
    """Generates preface, dedication, and table of contents."""
    chapters = outline.get("chapters", [])
    toc = "\n".join([f"  Chapter {c['number']}: {c['title']}" for c in chapters])

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": f"""Write the front matter for this book:

Title: {book_title}
Genre: {concept.get('genre', 'Non-fiction')}
Promise: {concept.get('transformation_promise', '')}
Target Reader: {concept.get('target_reader_identity', '')}

Write in this order, clearly separated:

1. DEDICATION (2-3 lines, heartfelt, speaks to the reader this book is for)
2. PREFACE (200-300 words — why this book exists, who it's for, what it will do for them)
3. TABLE OF CONTENTS:
{toc}

Use markdown formatting."""}]
    )
    return response.content[0].text


def generate_back_matter(book_title: str, concept: dict) -> str:
    """Generates about the author, review request, and resources page."""
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": f"""Write the back matter for this book:

Title: {book_title}
Genre: {concept.get('genre', 'Non-fiction')}
Promise: {concept.get('transformation_promise', '')}

Write in this order:

1. A NOTE FROM THE AUTHOR (100-150 words — warm, personal closing that reinforces transformation)
2. LEAVE A REVIEW (50 words — friendly ask for an honest Amazon review, explain it helps other readers find the book)
3. RESOURCES & RECOMMENDED READING (list 5-8 real books/resources relevant to this topic)

Use markdown formatting."""}]
    )
    return response.content[0].text


# ── Continuity Check ─────────────────────────────────────────────────────────

def run_continuity_check(book_dir: str, book_title: str) -> dict:
    """Scans all chapters for inconsistencies. Returns structured report."""
    chapter_files = sorted([f for f in os.listdir(book_dir)
                            if f.startswith("chapter_") and f.endswith(".md") and "_edited" not in f and "_original" not in f])

    if not chapter_files:
        return {"score": 1.0, "issues": [], "recommendation": "No chapters found."}

    # Build a condensed view: first 800 chars of each chapter
    chapter_previews = ""
    for cf in chapter_files:
        with open(os.path.join(book_dir, cf), encoding="utf-8", errors="replace") as f:
            content = f.read()
        chapter_previews += f"\n\n--- {cf} ---\n{content[:800]}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=CONTINUITY_SYSTEM,
        messages=[{"role": "user", "content": f"""Check this manuscript for continuity issues:

Book: {book_title}

{chapter_previews}

Return valid JSON only."""}]
    )

    text = response.content[0].text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"score": 0.5, "issues": [], "recommendation": text}


# ── File I/O ─────────────────────────────────────────────────────────────────

def save_chapter(book_title: str, chapter_number: int, chapter_title: str, content: str) -> str:
    book_slug = _slugify(book_title)
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    os.makedirs(book_dir, exist_ok=True)
    filename = f"chapter_{chapter_number:02d}_{_slugify(chapter_title, 30)}.md"
    filepath = os.path.join(book_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Chapter {chapter_number}: {chapter_title}\n\n{content}")
    return filepath


def save_outline(book_title: str, outline: dict) -> str:
    book_slug = _slugify(book_title)
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    os.makedirs(book_dir, exist_ok=True)
    filepath = os.path.join(book_dir, "00_outline.json")
    with open(filepath, "w") as f:
        json.dump(outline, f, indent=2)
    return f"Outline saved: {filepath}"


def save_bible(book_title: str, bible: str, style_guide: str):
    book_slug = _slugify(book_title)
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    with open(os.path.join(book_dir, "00_character_bible.md"), "w", encoding="utf-8") as f:
        f.write(bible)
    with open(os.path.join(book_dir, "00_style_guide.md"), "w", encoding="utf-8") as f:
        f.write(style_guide)


# ── Tool handling ─────────────────────────────────────────────────────────────

WRITING_TOOLS = [
    {
        "name": "write_chapter",
        "description": "Writes a complete book chapter",
        "input_schema": {
            "type": "object",
            "properties": {
                "chapter_number": {"type": "integer"},
                "chapter_title": {"type": "string"},
                "chapter_goal": {"type": "string"},
                "opening_story": {"type": "string"},
                "core_content": {"type": "string"},
                "word_count_target": {"type": "integer"},
                "chapter_text": {"type": "string"},
            },
            "required": ["chapter_number", "chapter_title", "chapter_goal", "chapter_text"]
        }
    },
    {
        "name": "generate_outline",
        "description": "Creates a detailed chapter-by-chapter book outline",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "genre": {"type": "string"},
                "transformation_promise": {"type": "string"},
                "total_chapters": {"type": "integer"},
                "chapters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "integer"},
                            "title": {"type": "string"},
                            "purpose": {"type": "string"},
                            "key_content": {"type": "array", "items": {"type": "string"}},
                            "emotional_beat": {"type": "string"},
                            "word_count": {"type": "integer"},
                        }
                    }
                }
            },
            "required": ["book_title", "genre", "transformation_promise", "total_chapters", "chapters"]
        }
    },
    {
        "name": "save_chapter",
        "description": "Saves a written chapter to the manuscript file",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "chapter_number": {"type": "integer"},
                "chapter_title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["book_title", "chapter_number", "chapter_title", "content"]
        }
    }
]


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "save_chapter":
        return save_chapter(
            tool_input["book_title"],
            tool_input["chapter_number"],
            tool_input["chapter_title"],
            tool_input["content"]
        )
    elif tool_name == "write_chapter":
        if "chapter_text" in tool_input:
            save_chapter("current_book", tool_input["chapter_number"],
                        tool_input["chapter_title"], tool_input["chapter_text"])
        return json.dumps({"status": "chapter_written", "chapter": tool_input["chapter_number"]})
    elif tool_name == "generate_outline":
        save_outline(tool_input["book_title"], tool_input)
        return json.dumps({"status": "outline_saved", "chapters": tool_input["total_chapters"]})
    return json.dumps({"status": "unknown_tool"})


# ── Core writing functions ────────────────────────────────────────────────────

def create_outline(concept: dict) -> dict:
    """Creates a full book outline from a Psychology Agent concept."""
    query = f"""Create a detailed chapter-by-chapter outline for this book:

    Title: {concept.get('working_title', 'Untitled')}
    Subtitle: {concept.get('subtitle', '')}
    Genre: {concept.get('genre', 'Non-fiction')}
    Target Reader: {concept.get('target_reader_identity', '')}
    Transformation Promise: {concept.get('transformation_promise', '')}
    Primary Emotion: {concept.get('primary_emotion', '')}

    Create an outline with 10–14 chapters that:
    1. Opens with a chapter that immediately makes the reader feel "this author understands me"
    2. Progresses through a clear emotional and practical journey
    3. Each chapter has a specific purpose AND an emotional beat
    4. Ends with a chapter that makes the reader feel genuinely transformed
    5. Word count per chapter: 3,000–5,000 for non-fiction; 4,000–6,000 for fiction

    Use generate_outline tool to structure and save the outline."""

    messages = [{"role": "user", "content": query}]
    output = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=WRITING_TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    output.append(block.text)
            break
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = process_tool_call(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})
            continue
        break

    return {"status": "complete", "outline": output}


def write_chapter(book_title: str, chapter_number: int, chapter_title: str,
                  chapter_brief: str, book_context: str = "",
                  character_bible: str = "", style_guide: str = "",
                  previous_summaries: list[str] = None) -> dict:
    """Writes a single chapter with full context awareness."""
    summaries_text = ""
    if previous_summaries:
        summaries_text = "\n\nPREVIOUS CHAPTERS SUMMARY (do NOT repeat these ideas):\n"
        for i, s in enumerate(previous_summaries, 1):
            summaries_text += f"Ch.{i}: {s}\n"

    query = f"""Write Chapter {chapter_number} of "{book_title}".

Chapter Title: {chapter_title}
Chapter Brief: {chapter_brief}
Book Context: {book_context}

STYLE GUIDE (follow strictly):
{style_guide}

CHARACTER/CONCEPT BIBLE (keep all names and facts consistent with this):
{character_bible}
{summaries_text}

Write the FULL chapter now — no summaries, no placeholders.
Target: 3,000–5,000 words for non-fiction; 4,000–6,000 for fiction.

Requirements:
- Open with a story or compelling scene (not a definition or thesis statement)
- Use specific examples, not vague generalities
- Include at least 2–3 moments where the reader would think "that's exactly how I feel"
- End with a chapter close that either gives a clear takeaway OR creates a hook to the next chapter
- DO NOT repeat concepts already covered in previous chapters (check summaries above)

Use save_chapter tool to save the completed chapter."""

    messages = [{"role": "user", "content": query}]
    output = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=8096,
            system=SYSTEM_PROMPT,
            tools=WRITING_TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    output.append(block.text)
            break
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = process_tool_call(block.name, block.input)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})
            continue
        break

    return {"status": "complete", "chapter": chapter_number, "content": output}


def write_full_book(concept: dict) -> dict:
    """Full pipeline: bible → style guide → outline → write all chapters → front/back matter → compile."""
    book_title = concept.get("working_title", "Untitled")
    print(f"\nWriting: {book_title}")

    # Step 1: Generate outline
    print("  → Generating outline...")
    create_outline(concept)

    book_slug = _slugify(book_title)
    outline_path = os.path.join(MANUSCRIPTS_DIR, book_slug, "00_outline.json")
    if not os.path.exists(outline_path):
        return {"status": "error", "message": "Outline not saved"}

    with open(outline_path) as f:
        outline = json.load(f)

    # Step 2: Build character bible & style guide
    print("  → Building character bible and style guide...")
    bible = build_character_bible(concept, outline)
    style_guide = build_style_guide(concept)
    save_bible(book_title, bible, style_guide)

    # Step 3: Generate front matter
    print("  → Generating front matter...")
    front = generate_front_matter(book_title, concept, outline)
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    with open(os.path.join(book_dir, "00_front_matter.md"), "w", encoding="utf-8") as f:
        f.write(front)

    # Step 4: Write chapters with rolling summaries
    chapters = outline.get("chapters", [])
    book_context = f"Book: {book_title}. Promise: {concept.get('transformation_promise', '')}."
    previous_summaries = []

    for ch in chapters:
        print(f"  → Writing Chapter {ch['number']}: {ch['title']}...")
        brief = f"Purpose: {ch.get('purpose')}. Key content: {', '.join(ch.get('key_content', []))}. Emotional beat: {ch.get('emotional_beat', '')}."
        result = write_chapter(
            book_title, ch["number"], ch["title"], brief, book_context,
            character_bible=bible, style_guide=style_guide,
            previous_summaries=previous_summaries
        )

        # Load written chapter and summarise it for next chapter
        chapter_files = [f for f in os.listdir(book_dir)
                        if f.startswith(f"chapter_{ch['number']:02d}_") and f.endswith(".md")]
        if chapter_files:
            with open(os.path.join(book_dir, chapter_files[0]), encoding="utf-8") as f:
                chapter_text = f.read()

            # Quality check — extend if too short
            if _word_count(chapter_text) < MIN_CHAPTER_WORDS:
                print(f"     ⚠ Chapter {ch['number']} is short — extending...")
                extended = extend_chapter(chapter_text, ch["title"], MIN_CHAPTER_WORDS, style_guide)
                with open(os.path.join(book_dir, chapter_files[0]), "w", encoding="utf-8") as f:
                    f.write(extended)
                chapter_text = extended

            summary = summarise_chapter(chapter_text, ch["number"])
            previous_summaries.append(summary)

    # Step 5: Back matter
    print("  → Generating back matter...")
    back = generate_back_matter(book_title, concept)
    with open(os.path.join(book_dir, "99_back_matter.md"), "w", encoding="utf-8") as f:
        f.write(back)

    # Step 6: Continuity check
    print("  → Running continuity check...")
    continuity = run_continuity_check(book_dir, book_title)
    score = continuity.get("score", 0)
    issues = continuity.get("issues", [])
    critical = [i for i in issues if i.get("severity") == "critical"]
    print(f"     Continuity score: {score:.0%} | Issues: {len(issues)} ({len(critical)} critical)")
    with open(os.path.join(book_dir, "00_continuity_report.json"), "w") as f:
        json.dump(continuity, f, indent=2)

    # Step 7: Compile
    compile_manuscript(book_title)

    return {"status": "complete", "book": book_title, "chapters": len(chapters),
            "continuity_score": score, "issues": len(issues)}


def compile_manuscript(book_title: str) -> str:
    """Combines front matter + chapters + back matter into one manuscript, then exports to Word."""
    book_slug = _slugify(book_title)
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    output_path = os.path.join(book_dir, f"FULL_MANUSCRIPT_{book_slug}.md")

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"# {book_title}\n\n---\n\n")

        # Front matter
        front_path = os.path.join(book_dir, "00_front_matter.md")
        if os.path.exists(front_path):
            with open(front_path, encoding="utf-8", errors="replace") as f:
                out.write(f.read() + "\n\n---\n\n")

        # Chapters
        chapter_files = sorted([f for f in os.listdir(book_dir)
                                if f.startswith("chapter_") and f.endswith(".md")
                                and "_edited" not in f and "_original" not in f])
        for cf in chapter_files:
            with open(os.path.join(book_dir, cf), encoding="utf-8", errors="replace") as ch:
                out.write(ch.read())
                out.write("\n\n---\n\n")

        # Back matter
        back_path = os.path.join(book_dir, "99_back_matter.md")
        if os.path.exists(back_path):
            with open(back_path, encoding="utf-8", errors="replace") as f:
                out.write(f.read())

    word_path = export_to_word(book_title, output_path)
    print(f"\n  [Publish] Word document ready: {word_path}")
    return f"Manuscript compiled: {output_path}"


def export_to_word(book_title: str, manuscript_path: str) -> str:
    """Converts the compiled markdown manuscript to a formatted Word .docx file."""
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return "python-docx not installed — run: pip install python-docx"

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
        elif line.startswith("### "):
            h = doc.add_heading(line[4:].strip(), level=3)
            if h.runs:
                h.runs[0].font.size = Pt(12)
        elif line.strip() == "---":
            doc.add_paragraph("─" * 40).alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif line.strip() == "":
            doc.add_paragraph()
        else:
            para = doc.add_paragraph()
            para.paragraph_format.space_after = Pt(6)
            pattern = re.compile(r'(\*\*.*?\*\*|\*.*?\*)')
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
    word_path = os.path.join(PUBLISH_DIR, f"{safe_title}.docx")
    doc.save(word_path)
    return word_path


if __name__ == "__main__":
    print("=== KDP Book Writing Agent ===")
    result = write_chapter(
        book_title="Chaos to Clarity",
        chapter_number=1,
        chapter_title="Why Every System You've Tried Has Failed You",
        chapter_brief="Open by validating the reader's frustration. Explain why traditional productivity systems are built for neurotypical brains. Introduce the ADHD brain architecture. End with hope.",
        book_context="Non-fiction self-help for adults with ADHD.",
    )
    print(f"Chapter written. Status: {result['status']}")
