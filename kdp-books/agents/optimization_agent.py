"""
AGENT 5: Optimization Agent
Creates KDP-optimized titles, subtitles, book descriptions, backend
keywords, and category selections. Maximizes discoverability and conversion.
"""

import anthropic
import json
import os
from datetime import datetime
from config import (ANTHROPIC_API_KEY, DEFAULT_MODEL, MARKETING_DIR,
                   KDP_MAX_KEYWORDS, KDP_CATEGORIES_PER_BOOK)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an Amazon KDP optimization specialist and conversion copywriter.

You maximize book discoverability and purchase conversion through:

TITLE OPTIMIZATION:
- Main title: memorable, benefit-driven, emotionally resonant (ideally 2–5 words)
- Subtitle: keyword-rich, specific promise, 8–15 words ideal
- Title formula examples:
  * [Outcome] for [Specific Audience]: [Method/Promise]
  * The [Adjective] [Noun]: [Transformation Promise]
  * [Number] [Things] That [Result]
  * [Provocative Statement]: [Clarification/Promise]

KEYWORD STRATEGY (7 backend keywords max):
- Mix broad + specific: 1 broad, 3 mid-tail, 3 long-tail
- Target keywords with high search volume but not dominated by massive publishers
- Include audience-specific phrases ("for women over 40", "for beginners", "for entrepreneurs")
- Think like the reader searching at 11pm — what exact phrase do they type?

BOOK DESCRIPTION (Amazon listing):
- ABCDE formula:
  A = Attention (hook line — one powerful sentence)
  B = Build (describe the reader's current pain/situation)
  C = Credibility (why this book/approach is different)
  D = Details (bullet-pointed benefits/chapters — what they'll get)
  E = End (call to action: "Scroll up and grab your copy")
- Use bold HTML tags for Amazon: <b>text</b>
- 150–400 words optimal
- Start with the reader, not with "In this book..."

CATEGORY STRATEGY:
- Find categories where BSR #1 = 20,000–100,000 (consistent but winnable)
- Select 2 main categories in KDP dashboard
- Request up to 8 more via email to KDP support
- Aim for categories where you can realistically hit top 20 within 3 months

PRICING STRATEGY:
- Non-fiction: $4.99–$7.99 ebook, $12.99–$16.99 paperback
- Fiction: $3.99–$5.99 ebook, $12.99–$14.99 paperback
- Avoid $0.99–$1.99 (signals poor quality in 2025–2026)
- Launch at lower end; increase after first 10 reviews"""

OPTIMIZATION_TOOLS = [
    {
        "name": "optimize_title",
        "description": "Generates 5 title/subtitle variations with analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_concept": {"type": "string"},
                "target_audience": {"type": "string"},
                "transformation_promise": {"type": "string"},
                "variations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "subtitle": {"type": "string"},
                            "formula_used": {"type": "string"},
                            "strength": {"type": "string"},
                            "keyword_richness": {"type": "integer"},
                        }
                    }
                },
                "recommended": {"type": "string"},
            },
            "required": ["book_concept", "variations", "recommended"]
        }
    },
    {
        "name": "generate_keywords",
        "description": "Generates 7 optimized backend keywords for KDP",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "genre": {"type": "string"},
                "target_audience": {"type": "string"},
                "keywords": {
                    "type": "array",
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "properties": {
                            "keyword": {"type": "string"},
                            "type": {"type": "string", "enum": ["broad", "mid-tail", "long-tail"]},
                            "rationale": {"type": "string"},
                        }
                    }
                }
            },
            "required": ["book_title", "keywords"]
        }
    },
    {
        "name": "write_description",
        "description": "Writes a fully optimized Amazon book description",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "description_text": {"type": "string", "description": "Full Amazon description with HTML formatting"},
                "word_count": {"type": "integer"},
                "hooks_used": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["book_title", "description_text", "word_count"]
        }
    },
    {
        "name": "recommend_categories",
        "description": "Recommends KDP categories with competition analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "primary_category": {"type": "string"},
                "secondary_category": {"type": "string"},
                "additional_categories": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                "category_strategy": {"type": "string"},
            },
            "required": ["book_title", "primary_category", "secondary_category"]
        }
    },
    {
        "name": "save_marketing_package",
        "description": "Saves the complete marketing package for a book",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "package": {"type": "object"},
            },
            "required": ["book_title", "package"]
        }
    }
]


import re

def _slugify(text: str, max_len: int = 40) -> str:
    slug = text.lower()
    slug = re.sub(r'[<>:"/\\|?*,\'!]', '', slug)
    slug = re.sub(r'\s+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug[:max_len]


def save_marketing_package(book_title: str, package: dict) -> str:
    book_slug = _slugify(book_title)
    filename = f"{book_slug}_marketing.json"
    filepath = os.path.join(MARKETING_DIR, filename)
    with open(filepath, "w") as f:
        json.dump({"book_title": book_title, "timestamp": datetime.now().isoformat(),
                  "package": package}, f, indent=2)

    # Also save a human-readable version
    readable_path = os.path.join(MARKETING_DIR, f"{book_slug}_listing.md")
    with open(readable_path, "w") as f:
        f.write(f"# Amazon KDP Listing: {book_title}\n\n")
        if "title_options" in package:
            f.write("## Title Options\n")
            for v in package.get("title_options", {}).get("variations", []):
                f.write(f"- **{v.get('title')}**: {v.get('subtitle')}\n")
            f.write(f"\n**Recommended**: {package.get('title_options', {}).get('recommended')}\n\n")
        if "keywords" in package:
            f.write("## Backend Keywords\n")
            for kw in package.get("keywords", []):
                f.write(f"- {kw.get('keyword')} ({kw.get('type')})\n")
            f.write("\n")
        if "description" in package:
            f.write("## Amazon Description\n\n")
            f.write(package.get("description", {}).get("description_text", ""))
            f.write("\n\n")
        if "categories" in package:
            f.write("## Categories\n")
            f.write(f"- Primary: {package.get('categories', {}).get('primary_category')}\n")
            f.write(f"- Secondary: {package.get('categories', {}).get('secondary_category')}\n")

    return f"Marketing package saved: {readable_path}"


def process_tool_call(tool_name: str, tool_input: dict, package: dict) -> str:
    if tool_name == "optimize_title":
        package["title_options"] = tool_input
        return json.dumps({"status": "titles_generated", "count": len(tool_input.get("variations", []))})
    elif tool_name == "generate_keywords":
        package["keywords"] = tool_input.get("keywords", [])
        return json.dumps({"status": "keywords_generated", "count": len(package["keywords"])})
    elif tool_name == "write_description":
        package["description"] = tool_input
        return json.dumps({"status": "description_written", "words": tool_input.get("word_count")})
    elif tool_name == "recommend_categories":
        package["categories"] = tool_input
        return json.dumps({"status": "categories_selected"})
    elif tool_name == "save_marketing_package":
        return save_marketing_package(tool_input["book_title"], tool_input["package"])
    return json.dumps({"status": "unknown_tool"})


def optimize_book(concept: dict) -> dict:
    """
    Full optimization pipeline for a book concept.
    Returns complete marketing package.
    """
    package = {}

    title = concept.get('working_title') or concept.get('title') or 'Untitled'
    genre = concept.get('genre') or 'Non-fiction'
    target_reader = concept.get('target_reader_identity') or concept.get('target_audience') or 'General adult readers'
    promise = concept.get('transformation_promise') or concept.get('premise') or ''
    emotion = concept.get('primary_emotion') or 'aspiration'
    desire = concept.get('desire_cluster') or 'growth'
    gender = concept.get('gender_primary') or 'both'
    age = concept.get('age_range') or '25-50'

    query = f"""Create a complete Amazon KDP optimization package for this book:

    Working Title: {title}
    Genre: {genre}
    Target Reader: {target_reader}
    Transformation Promise: {promise}
    Primary Emotion: {emotion}
    Desire Cluster: {desire}
    Gender Primary: {gender}
    Age Range: {age}

    Complete ALL of the following using the provided tools:

    1. optimize_title — generate 5 title/subtitle variations, recommend the best
    2. generate_keywords — create the 7 backend keywords (1 broad, 3 mid-tail, 3 long-tail)
    3. write_description — write the full Amazon listing description (ABCDE formula, 200–350 words, use <b> tags)
    4. recommend_categories — select primary, secondary, and up to 8 additional KDP categories
    5. save_marketing_package — save everything together

    Be specific and commercial. Think like a reader who's about to spend $5.99 on this."""

    messages = [{"role": "user", "content": query}]
    output = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=OPTIMIZATION_TOOLS,
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
                    result = process_tool_call(block.name, block.input, package)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    return {"status": "complete", "package": package, "summary": output}


if __name__ == "__main__":
    print("=== KDP Optimization Agent ===")
    test_concept = {
        "working_title": "Chaos to Clarity",
        "subtitle": "The ADHD Productivity System That Actually Works for Adults",
        "genre": "Non-fiction / Self-Help",
        "target_reader_identity": "An adult with ADHD who has failed every productivity system they've tried",
        "transformation_promise": "From chronic chaos and shame about productivity to a personalized system that works with your ADHD brain",
        "primary_emotion": "shame",
        "desire_cluster": "identity",
        "gender_primary": "both",
        "age_range": "25-45",
    }
    result = optimize_book(test_concept)
    print("Optimization complete.")
    if result["summary"]:
        print(result["summary"][0])
