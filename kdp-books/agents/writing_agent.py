"""
AGENT 4: Book Writing Agent
Writes full books aligned with Amazon KDP standards using proven
structures, psychological triggers, and market-tested frameworks.
Produces chapter-by-chapter manuscripts ready for formatting.
"""

import anthropic
import json
import os
from datetime import datetime
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MANUSCRIPTS_DIR

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
- Front matter: title page, copyright, table of contents, dedication (optional)
- Back matter: about the author, other books, review request, resources
- Non-fiction: 30,000–70,000 words ideal range
- Fiction: 60,000–100,000 words for most genres; 40,000+ minimum"""

WRITING_TOOLS = [
    {
        "name": "write_chapter",
        "description": "Writes a complete book chapter",
        "input_schema": {
            "type": "object",
            "properties": {
                "chapter_number": {"type": "integer"},
                "chapter_title": {"type": "string"},
                "chapter_goal": {"type": "string", "description": "What the reader learns/feels by end of chapter"},
                "opening_story": {"type": "string", "description": "Brief description of the opening story/hook"},
                "core_content": {"type": "string", "description": "Main teaching, argument, or narrative content"},
                "word_count_target": {"type": "integer"},
                "chapter_text": {"type": "string", "description": "The full written chapter text"},
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


def save_chapter(book_title: str, chapter_number: int, chapter_title: str, content: str) -> str:
    book_slug = book_title.lower().replace(" ", "_")[:40]
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    os.makedirs(book_dir, exist_ok=True)
    filename = f"chapter_{chapter_number:02d}_{chapter_title.lower().replace(' ', '_')[:30]}.md"
    filepath = os.path.join(book_dir, filename)
    with open(filepath, "w") as f:
        f.write(f"# Chapter {chapter_number}: {chapter_title}\n\n{content}")
    return f"Chapter saved: {filepath}"


def save_outline(book_title: str, outline: dict) -> str:
    book_slug = book_title.lower().replace(" ", "_")[:40]
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    os.makedirs(book_dir, exist_ok=True)
    filepath = os.path.join(book_dir, "00_outline.json")
    with open(filepath, "w") as f:
        json.dump(outline, f, indent=2)
    return f"Outline saved: {filepath}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "save_chapter":
        return save_chapter(
            tool_input["book_title"],
            tool_input["chapter_number"],
            tool_input["chapter_title"],
            tool_input["content"]
        )
    elif tool_name == "write_chapter":
        # Auto-save when chapter is written
        if "chapter_text" in tool_input:
            save_chapter("current_book", tool_input["chapter_number"],
                        tool_input["chapter_title"], tool_input["chapter_text"])
        return json.dumps({"status": "chapter_written", "chapter": tool_input["chapter_number"]})
    elif tool_name == "generate_outline":
        save_outline(tool_input["book_title"], tool_input)
        return json.dumps({"status": "outline_saved", "chapters": tool_input["total_chapters"]})
    return json.dumps({"status": "unknown_tool"})


def create_outline(concept: dict) -> dict:
    """Creates a full book outline from a Psychology Agent concept."""
    query = f"""Create a detailed chapter-by-chapter outline for this book:

    Title: {concept.get('working_title', 'Untitled')}
    Subtitle: {concept.get('subtitle', '')}
    Genre: {concept.get('genre', 'Non-fiction')}
    Target Reader: {concept.get('target_reader_identity', '')}
    Transformation Promise: {concept.get('transformation_promise', '')}
    Primary Emotion: {concept.get('primary_emotion', '')}
    Desire Cluster: {concept.get('desire_cluster', '')}

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
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    return {"status": "complete", "outline": output}


def write_chapter(book_title: str, chapter_number: int, chapter_title: str,
                  chapter_brief: str, book_context: str = "") -> dict:
    """Writes a single chapter. Called iteratively to build the full manuscript."""
    query = f"""Write Chapter {chapter_number} of "{book_title}".

    Chapter Title: {chapter_title}
    Chapter Brief: {chapter_brief}
    Book Context: {book_context}

    Write the FULL chapter now — no summaries, no placeholders.
    Target: 3,000–5,000 words for non-fiction; 4,000–6,000 for fiction.

    Requirements:
    - Open with a story or compelling scene (not a definition or thesis statement)
    - Use specific examples, not vague generalities
    - Include at least 2–3 moments where the reader would think "that's exactly how I feel"
    - End with a chapter close that either gives a clear takeaway OR creates a hook to the next chapter
    - Write in a warm, direct, conversational voice — like a knowledgeable friend

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
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    return {"status": "complete", "chapter": chapter_number, "content": output}


def write_full_book(concept: dict) -> dict:
    """
    Full pipeline: outline → write all chapters → save manuscript.
    This is the main function called by the Automation Agent.
    """
    book_title = concept.get("working_title", "Untitled")
    print(f"\nWriting: {book_title}")

    # Step 1: Generate outline
    print("  → Generating outline...")
    outline_result = create_outline(concept)

    # Step 2: Load saved outline
    book_slug = book_title.lower().replace(" ", "_")[:40]
    outline_path = os.path.join(MANUSCRIPTS_DIR, book_slug, "00_outline.json")

    if not os.path.exists(outline_path):
        return {"status": "error", "message": "Outline not saved properly"}

    with open(outline_path) as f:
        outline = json.load(f)

    chapters = outline.get("chapters", [])
    book_context = f"Book: {book_title}. Promise: {concept.get('transformation_promise', '')}."

    # Step 3: Write each chapter
    for ch in chapters:
        print(f"  → Writing Chapter {ch['number']}: {ch['title']}...")
        brief = f"Purpose: {ch.get('purpose')}. Key content: {', '.join(ch.get('key_content', []))}. Emotional beat: {ch.get('emotional_beat', '')}."
        write_chapter(book_title, ch["number"], ch["title"], brief, book_context)

    # Step 4: Compile full manuscript
    compile_manuscript(book_title)

    return {"status": "complete", "book": book_title, "chapters": len(chapters)}


def compile_manuscript(book_title: str) -> str:
    """Combines all chapter files into one complete manuscript."""
    book_slug = book_title.lower().replace(" ", "_")[:40]
    book_dir = os.path.join(MANUSCRIPTS_DIR, book_slug)
    output_path = os.path.join(book_dir, f"FULL_MANUSCRIPT_{book_slug}.md")

    chapter_files = sorted([f for f in os.listdir(book_dir)
                            if f.startswith("chapter_") and f.endswith(".md")])

    with open(output_path, "w") as out:
        out.write(f"# {book_title}\n\n---\n\n")
        for cf in chapter_files:
            with open(os.path.join(book_dir, cf)) as ch:
                out.write(ch.read())
                out.write("\n\n---\n\n")

    return f"Manuscript compiled: {output_path}"


if __name__ == "__main__":
    print("=== KDP Book Writing Agent ===")
    # Example: write a chapter standalone
    result = write_chapter(
        book_title="Chaos to Clarity",
        chapter_number=1,
        chapter_title="Why Every System You've Tried Has Failed You",
        chapter_brief="Open by validating the reader's frustration. Explain why traditional productivity systems are built for neurotypical brains. Introduce the ADHD brain architecture. End with hope: a different approach is coming.",
        book_context="Non-fiction self-help for adults with ADHD who've failed every productivity system."
    )
    print(f"Chapter written. Status: {result['status']}")
