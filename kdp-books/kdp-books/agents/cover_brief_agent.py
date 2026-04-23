"""
Cover Brief Agent — V3 Core Pipeline
Takes a book idea (from book_idea_generator output) and produces a complete,
designer-ready cover brief: color palette, typography, imagery direction,
mood board references, and KDP technical specs.

Runs automatically after book_idea_generator, or standalone for any book.

Standalone:
  python cover_brief_agent.py                          # uses top-ranked idea
  python cover_brief_agent.py --idea "The Man She Stays For"
  python cover_brief_agent.py --file book-ideas/top_ideas_20260423.json --rank 2
"""

import json
import os
import argparse
from pathlib import Path
from datetime import datetime
from config import get_client, DEFAULT_MODEL

client  = get_client()

AGENTS_DIR = Path(__file__).parent
IDEAS_DIR  = AGENTS_DIR.parent / "book-ideas"
MEMORY_DIR = AGENTS_DIR / "memory"
OUTPUT_DIR = AGENTS_DIR / "output"


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_latest_idea(rank: int = 1) -> dict | None:
    """Load the top-ranked idea from the most recent ideas file."""
    files = sorted(IDEAS_DIR.glob("top_ideas_*.json"), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        data = json.load(f)
    ideas = data.get("ideas", [])
    for idea in ideas:
        if idea.get("rank") == rank:
            return idea
    return ideas[0] if ideas else None


def load_idea_by_title(title: str) -> dict | None:
    """Search all ideas files for one matching the given title."""
    for f in sorted(IDEAS_DIR.glob("top_ideas_*.json"), reverse=True):
        with open(f) as fh:
            data = json.load(fh)
        for idea in data.get("ideas", []):
            if title.lower() in idea.get("working_title", "").lower():
                return idea
    return None


def load_idea_from_file(filepath: str, rank: int = 1) -> dict | None:
    with open(filepath) as f:
        data = json.load(f)
    ideas = data.get("ideas", [])
    for idea in ideas:
        if idea.get("rank") == rank:
            return idea
    return ideas[0] if ideas else None


# ── Core Agent ────────────────────────────────────────────────────────────────

def generate_cover_brief(idea: dict) -> dict:
    """
    Generate a complete designer-ready cover brief for one book idea.

    Args:
        idea: A single idea dict from book_idea_generator output.

    Returns:
        Full cover brief dict.
    """
    system_prompt = """You are a senior book cover art director with 15 years of experience
designing bestselling nonfiction covers. You understand that a cover must:
1. Stop a reader scrolling thumbnails on Amazon at 200x300px
2. Signal the genre and tone in under 2 seconds
3. Communicate the core promise without the reader reading the subtitle
4. Differentiate from the top 10 competitors in the category

You write cover briefs that a professional designer can execute immediately —
no vague instructions, no mood words without specifics. Every direction has a reason.
Output valid JSON only."""

    user_prompt = f"""Create a complete, designer-ready cover brief for this book.

BOOK IDEA:
{json.dumps(idea, indent=2)}

Think carefully about:
- The target reader: what visual language speaks to them?
- The genre signals: what does this category's cover language look like?
- The competitors: how does this cover stand out while still belonging on the same shelf?
- The thumbnail test: will this read clearly at 200x300px on a phone screen?
- The tone: does the visual match the book's emotional register?

Return this exact JSON:

{{
  "book_title": "{idea.get('working_title', '')}",
  "brief_version": "v1",
  "generated_at": "{datetime.utcnow().isoformat()}",

  "concept": {{
    "one_line_concept": "<the cover idea in one sentence — e.g. 'Two silhouettes facing each other in dark blue fog'>",
    "emotional_register": "<the feeling the cover must produce in 2 seconds — e.g. 'quiet authority', 'urgent clarity'>",
    "genre_signals": ["<visual cue that says this is [genre]>", ...],
    "differentiation": "<specifically how this differs from top competitors>"
  }},

  "color_palette": {{
    "primary": {{
      "hex": "<#XXXXXX>",
      "role": "<dominant background or hero color>",
      "rationale": "<why this color for this book and reader>"
    }},
    "secondary": {{
      "hex": "<#XXXXXX>",
      "role": "<supporting color>",
      "rationale": "<why>"
    }},
    "accent": {{
      "hex": "<#XXXXXX>",
      "role": "<title text, highlights, or key element>",
      "rationale": "<why>"
    }},
    "text_on_cover": "<#XXXXXX>",
    "palette_mood": "<2-3 words describing the combined palette feel>",
    "palette_rationale": "<one sentence on why this palette fits the book and reader>"
  }},

  "typography": {{
    "title_font": {{
      "name": "<font name>",
      "weight": "<Bold / SemiBold / Light>",
      "style": "<all caps / title case / mixed>",
      "size_guidance": "<dominant / large / standard — relative to cover>",
      "tracking": "<tight / normal / wide>",
      "rationale": "<why this font for this book>"
    }},
    "subtitle_font": {{
      "name": "<font name — same or different from title>",
      "weight": "<weight>",
      "style": "<style>",
      "size_guidance": "<smaller than title — guidance on hierarchy>",
      "rationale": "<why>"
    }},
    "author_font": {{
      "name": "<font name>",
      "weight": "<weight>",
      "placement": "<bottom / top / other>"
    }},
    "font_pairing_rationale": "<why these fonts work together and fit the genre>",
    "fonts_to_avoid": ["<font to never use and why>", ...]
  }},

  "imagery": {{
    "style": "<photographic / illustrated / typographic / abstract / mixed>",
    "primary_visual": "<precise description of the main image or graphic element>",
    "secondary_elements": ["<supporting visual element>", ...],
    "what_to_show": "<what must appear on this cover>",
    "what_to_avoid": "<what must NOT appear — clichés, misleading signals>",
    "human_figures": "<yes/no — and if yes, how: silhouette, close-up, full body, no face>",
    "background_treatment": "<solid / gradient / texture / photo — with specifics>",
    "lighting_mood": "<dark and moody / bright and clean / high contrast / soft>",
    "stock_photo_direction": "<if using stock: exact search terms to find the right image>",
    "ai_image_prompt": "<ready-to-use prompt for image generation — specific and detailed>"
  }},

  "layout": {{
    "title_placement": "<top / center / bottom / overlaid on image>",
    "subtitle_placement": "<placement relative to title>",
    "image_placement": "<full bleed / inset / bottom half / top half / background>",
    "visual_hierarchy": "<what the eye sees first, second, third>",
    "whitespace_use": "<minimal / generous / intentional — with guidance>",
    "spine_color": "<hex and guidance for spine if paperback>",
    "back_cover_tone": "<brief guidance on back cover visual direction>"
  }},

  "kdp_technical_specs": {{
    "trim_size": "6 x 9 inches (standard nonfiction)",
    "cover_file_format": "PDF or JPEG, 300 DPI minimum",
    "full_cover_wrap": "Front + spine + back as single file for paperback",
    "ebook_cover": "2560 x 1600px, RGB, JPEG or TIFF",
    "safe_zone": "0.25 inch bleed on all edges, keep text 0.5 inch from trim",
    "spine_width_note": "Depends on page count: approx 0.002252 inches per page (white paper)",
    "isbn_barcode": "Required on back cover, white or light background, bottom right"
  }},

  "mood_board_references": {{
    "competitor_covers_to_study": ["<Title by Author — what to observe>", ...],
    "covers_to_beat": ["<Title by Author — what this cover must outperform>", ...],
    "visual_references_outside_books": ["<film poster / brand / photography style to reference>", ...]
  }},

  "designer_notes": "<2-3 sentences of direct guidance to the designer — most important priorities, common mistakes to avoid, what success looks like for this specific cover>",

  "a_b_test_variant": {{
    "concept": "<brief description of an alternative concept worth testing>",
    "key_difference": "<what is different from the primary concept>"
  }}
}}"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── Save & Format ─────────────────────────────────────────────────────────────

def save_cover_brief(brief: dict) -> tuple[Path, Path]:
    """Save the cover brief as JSON and a readable Markdown handoff doc."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str    = datetime.utcnow().strftime("%Y%m%d_%H%M")
    title_slug  = brief.get("book_title", "book").lower().replace(" ", "_")[:30]

    json_path = OUTPUT_DIR / f"cover_brief_{title_slug}_{date_str}.json"
    md_path   = OUTPUT_DIR / f"cover_brief_{title_slug}_{date_str}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2)

    # Build readable Markdown handoff doc
    c  = brief.get("concept", {})
    cp = brief.get("color_palette", {})
    ty = brief.get("typography", {})
    im = brief.get("imagery", {})
    ly = brief.get("layout", {})
    mb = brief.get("mood_board_references", {})
    ab = brief.get("a_b_test_variant", {})

    lines = [
        f"# Cover Brief — {brief.get('book_title', '')}",
        f"*Generated {datetime.utcnow().strftime('%d %B %Y')} · {brief.get('brief_version', 'v1')}*",
        "",
        "---",
        "",
        "## Concept",
        f"**One-line concept:** {c.get('one_line_concept', '')}",
        "",
        f"**Emotional register:** {c.get('emotional_register', '')}",
        "",
        f"**Differentiation:** {c.get('differentiation', '')}",
        "",
        f"**Genre signals:** {', '.join(c.get('genre_signals', []))}",
        "",
        "---",
        "",
        "## Color Palette",
        "",
        f"| Role | Hex | Purpose |",
        f"|---|---|---|",
        f"| Primary | `{cp.get('primary', {}).get('hex', '')}` | {cp.get('primary', {}).get('role', '')} |",
        f"| Secondary | `{cp.get('secondary', {}).get('hex', '')}` | {cp.get('secondary', {}).get('role', '')} |",
        f"| Accent | `{cp.get('accent', {}).get('hex', '')}` | {cp.get('accent', {}).get('role', '')} |",
        f"| Text on cover | `{cp.get('text_on_cover', '')}` | All cover text |",
        "",
        f"**Mood:** {cp.get('palette_mood', '')}",
        "",
        f"**Rationale:** {cp.get('palette_rationale', '')}",
        "",
        "---",
        "",
        "## Typography",
        "",
        f"**Title font:** {ty.get('title_font', {}).get('name', '')} · {ty.get('title_font', {}).get('weight', '')} · {ty.get('title_font', {}).get('style', '')}",
        f"*{ty.get('title_font', {}).get('rationale', '')}*",
        "",
        f"**Subtitle font:** {ty.get('subtitle_font', {}).get('name', '')} · {ty.get('subtitle_font', {}).get('weight', '')}",
        "",
        f"**Author font:** {ty.get('author_font', {}).get('name', '')} · {ty.get('author_font', {}).get('placement', '')}",
        "",
        f"**Pairing rationale:** {ty.get('font_pairing_rationale', '')}",
        "",
        f"**Fonts to avoid:** {', '.join(ty.get('fonts_to_avoid', []))}",
        "",
        "---",
        "",
        "## Imagery",
        "",
        f"**Style:** {im.get('style', '')}",
        "",
        f"**Primary visual:** {im.get('primary_visual', '')}",
        "",
        f"**Human figures:** {im.get('human_figures', '')}",
        "",
        f"**Background:** {im.get('background_treatment', '')}",
        "",
        f"**Lighting:** {im.get('lighting_mood', '')}",
        "",
        f"**What to show:** {im.get('what_to_show', '')}",
        "",
        f"**What to avoid:** {im.get('what_to_avoid', '')}",
        "",
        f"**Stock photo search terms:** {im.get('stock_photo_direction', '')}",
        "",
        "### AI Image Generation Prompt",
        f"```",
        im.get('ai_image_prompt', ''),
        "```",
        "",
        "---",
        "",
        "## Layout",
        "",
        f"**Title placement:** {ly.get('title_placement', '')}",
        f"**Subtitle placement:** {ly.get('subtitle_placement', '')}",
        f"**Image placement:** {ly.get('image_placement', '')}",
        f"**Visual hierarchy:** {ly.get('visual_hierarchy', '')}",
        f"**Whitespace:** {ly.get('whitespace_use', '')}",
        f"**Spine color:** {ly.get('spine_color', '')}",
        "",
        "---",
        "",
        "## KDP Technical Specs",
        "",
    ]

    for k, v in brief.get("kdp_technical_specs", {}).items():
        lines.append(f"- **{k.replace('_', ' ').title()}:** {v}")

    lines += [
        "",
        "---",
        "",
        "## Mood Board References",
        "",
        "**Covers to study:**",
    ]
    for ref in mb.get("competitor_covers_to_study", []):
        lines.append(f"- {ref}")

    lines += ["", "**Covers to beat:**"]
    for ref in mb.get("covers_to_beat", []):
        lines.append(f"- {ref}")

    lines += ["", "**Visual references outside books:**"]
    for ref in mb.get("visual_references_outside_books", []):
        lines.append(f"- {ref}")

    lines += [
        "",
        "---",
        "",
        "## Designer Notes",
        "",
        brief.get("designer_notes", ""),
        "",
        "---",
        "",
        "## A/B Test Variant",
        "",
        f"**Concept:** {ab.get('concept', '')}",
        f"**Key difference:** {ab.get('key_difference', '')}",
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def print_summary(brief: dict):
    c  = brief.get("concept", {})
    cp = brief.get("color_palette", {})
    ty = brief.get("typography", {})
    im = brief.get("imagery", {})

    print(f"\n{'='*60}")
    print(f"🎨 Cover Brief — {brief.get('book_title', '')}")
    print(f"{'='*60}")
    print(f"\n  Concept      : {c.get('one_line_concept', '')}")
    print(f"  Emotional    : {c.get('emotional_register', '')}")
    print(f"\n  Palette")
    print(f"    Primary    : {cp.get('primary', {}).get('hex', '')}  ({cp.get('primary', {}).get('role', '')})")
    print(f"    Secondary  : {cp.get('secondary', {}).get('hex', '')}  ({cp.get('secondary', {}).get('role', '')})")
    print(f"    Accent     : {cp.get('accent', {}).get('hex', '')}  ({cp.get('accent', {}).get('role', '')})")
    print(f"    Mood       : {cp.get('palette_mood', '')}")
    print(f"\n  Typography")
    print(f"    Title      : {ty.get('title_font', {}).get('name', '')} {ty.get('title_font', {}).get('weight', '')}")
    print(f"    Subtitle   : {ty.get('subtitle_font', {}).get('name', '')} {ty.get('subtitle_font', {}).get('weight', '')}")
    print(f"\n  Imagery")
    print(f"    Style      : {im.get('style', '')}")
    print(f"    Primary    : {im.get('primary_visual', '')}")
    print(f"    Lighting   : {im.get('lighting_mood', '')}")
    print(f"\n  Designer Notes:")
    print(f"    {brief.get('designer_notes', '')}")


# ── Main entry point ──────────────────────────────────────────────────────────

def run(idea: dict | None = None, rank: int = 1, idea_file: str | None = None) -> dict:
    """
    Generate and save a cover brief.
    Called by langgraph_orchestrator.py and standalone.

    Args:
        idea:      Pre-loaded idea dict (used when called from orchestrator).
        rank:      Which ranked idea to use if loading from file.
        idea_file: Specific ideas JSON file to load from.

    Returns:
        Full cover brief dict.
    """
    if idea is None:
        if idea_file:
            idea = load_idea_from_file(idea_file, rank)
        else:
            idea = load_latest_idea(rank)

    if not idea:
        print("⚠️  No book idea found. Run book_idea_generator.py first.")
        return {}

    print(f"\n🎨 Cover Brief Agent — generating brief for: {idea.get('working_title', '')}")
    brief = generate_cover_brief(idea)
    json_path, md_path = save_cover_brief(brief)
    print_summary(brief)
    print(f"\n   JSON   → {json_path}")
    print(f"   Report → {md_path}")

    return brief


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cover Brief Agent")
    parser.add_argument("--idea",  default=None, help="Book title to search for in ideas files")
    parser.add_argument("--file",  default=None, help="Specific top_ideas JSON file to use")
    parser.add_argument("--rank",  type=int, default=1, help="Which ranked idea to brief (default: 1)")
    args = parser.parse_args()

    if args.idea:
        loaded = load_idea_by_title(args.idea)
        if not loaded:
            print(f"No idea found matching '{args.idea}'")
            exit(1)
        run(idea=loaded)
    else:
        run(rank=args.rank, idea_file=args.file)
