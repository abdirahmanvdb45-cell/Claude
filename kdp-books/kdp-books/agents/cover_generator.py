"""
Cover Generator Agent — V3 Core Pipeline
Generates the actual book cover PNG from the cover brief's AI image prompt.

IMPORTANT: This agent only runs at the publish stage — after the manuscript
is fully written, continuity-checked, commercially approved, and the author
name is confirmed. It does NOT run during planning or drafting.

The gate is enforced by checking run_state.json for stage == "publish_ready".

Standalone (for the current book):
  python cover_generator.py --title "The Man She Stays For" --author "Your Name"

Force generate (skip gate — for testing):
  python cover_generator.py --force --author "Your Name"
"""

import json
import subprocess
import argparse
import sys
from pathlib import Path
from datetime import datetime
from config import get_client, DEFAULT_MODEL

client     = get_client()
AGENTS_DIR = Path(__file__).parent
MEMORY_DIR = AGENTS_DIR / "memory"
OUTPUT_DIR = AGENTS_DIR / "output"
COVERS_DIR = AGENTS_DIR.parent / "covers"


# ── Gate check ───────────────────────────────────────────────────────────────

def check_publish_gate(force: bool = False) -> tuple[bool, str]:
    """
    Only allow cover generation when the manuscript is publish-ready.
    Returns (allowed: bool, reason: str).
    """
    if force:
        return True, "Force flag set — skipping gate."

    state_path = MEMORY_DIR / "run_state.json"
    if not state_path.exists():
        return False, "No run_state.json found. Pipeline has not been run yet."

    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    stage = state.get("stage", "")

    # Must be at publish_ready or complete stage
    if stage not in ("publish_ready", "complete"):
        return False, (
            f"Manuscript is not ready for a cover yet.\n"
            f"   Current stage : {stage}\n"
            f"   Cover generation is locked until stage = 'publish_ready'.\n"
            f"   Finish writing and approving all chapters first."
        )

    # Check all chapters approved
    total    = state.get("total_chapters", 0)
    approved = [k for k in state.get("approved", {}) if k.startswith("chapter_")]
    if total > 0 and len(approved) < total:
        return False, (
            f"Not all chapters are approved.\n"
            f"   Approved : {len(approved)} / {total} chapters.\n"
            f"   Complete all chapters before generating the cover."
        )

    # Check commercial readiness passed
    commercial_path = OUTPUT_DIR / "commercial_readiness.json"
    if commercial_path.exists():
        with open(commercial_path, encoding="utf-8") as f:
            commercial = json.load(f)
        if not commercial.get("go_to_packaging"):
            return False, (
                "Commercial readiness check not passed.\n"
                "   Review output/commercial_readiness.json and fix packaging issues first."
            )

    return True, "All gates passed — manuscript is publish-ready."


# ── Load brief ────────────────────────────────────────────────────────────────

def load_cover_brief(title: str | None = None) -> dict | None:
    """Load the most relevant cover brief from output/."""
    briefs = sorted(OUTPUT_DIR.glob("cover_brief_*.json"), reverse=True)
    if not briefs:
        return None

    if title:
        slug = title.lower().replace(" ", "_")[:30]
        for b in briefs:
            if slug[:10] in b.name:
                with open(b, encoding="utf-8") as f:
                    return json.load(f)

    # Fall back to most recent
    with open(briefs[0], encoding="utf-8") as f:
        return json.load(f)


# ── Prompt refinement ─────────────────────────────────────────────────────────

def refine_prompt_for_kdp(brief: dict, author_name: str) -> str:
    """
    Take the brief's ai_image_prompt and refine it specifically for KDP cover
    dimensions and thumbnail readability. Adds typography direction for the
    image model, author name, and KDP aspect ratio guidance.
    """
    base_prompt     = brief.get("imagery", {}).get("ai_image_prompt", "")
    title           = brief.get("book_title", "")
    palette         = brief.get("color_palette", {})
    primary_hex     = palette.get("primary", {}).get("hex", "")
    accent_hex      = palette.get("accent", {}).get("hex", "")
    title_font      = brief.get("typography", {}).get("title_font", {}).get("name", "bold sans-serif")
    emotional       = brief.get("concept", {}).get("emotional_register", "")
    layout          = brief.get("layout", {})
    title_placement = layout.get("title_placement", "top")

    system_prompt = """You are a book cover art director preparing an AI image generation prompt
for a KDP nonfiction book cover. You specialise in prompts that produce covers that:
- read clearly as a thumbnail at 200x300px
- have strong visual hierarchy with text legible over the image
- look professionally published, not AI-generated

Output a single refined prompt string only. No JSON, no explanation."""

    user_prompt = f"""Refine this cover image prompt for a KDP book cover.

BOOK TITLE: {title}
AUTHOR NAME: {author_name}
BASE PROMPT: {base_prompt}
PRIMARY COLOR: {primary_hex}
ACCENT COLOR: {accent_hex}
TITLE FONT STYLE: {title_font}
EMOTIONAL REGISTER: {emotional}
TITLE PLACEMENT: {title_placement}

Requirements for the refined prompt:
1. Aspect ratio must be 2:3 (portrait — standard book cover)
2. The image must leave clear space for text overlay where the title will sit ({title_placement})
3. Background must be dark enough or light enough for white or black title text to be legible
4. No text should appear IN the generated image — text is added separately by the designer
5. The image must read as a professional nonfiction book cover at thumbnail size
6. Include the dominant color scheme: {primary_hex} as the primary, {accent_hex} as accent
7. End the prompt with: "professional book cover photography, editorial quality, 4K, sharp"

Return only the refined prompt text."""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    return response.content[0].text.strip()


# ── Image generation ──────────────────────────────────────────────────────────

def generate_cover_image(prompt: str, filename: str) -> Path | None:
    """
    Call the image generation tool to produce the cover PNG.
    Uses nano_banana_pro for highest quality (book cover — worth the extra quality).
    Returns the path to the generated file, or None on failure.
    """
    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = COVERS_DIR / filename
    payload     = json.dumps({
        "prompt":       prompt,
        "filename":     str(output_path.with_suffix("")),  # tool adds .png
        "aspect_ratio": "9:16",   # portrait — closest to book cover 2:3
        "model":        "nano_banana_pro",
    })

    print(f"\n   Generating cover image (this takes ~30 seconds)...")

    result = subprocess.run(
        ["asi-generate-image", payload],
        capture_output=True,
        text=True,
        env={**__import__("os").environ},
    )

    # The tool saves the file directly — check if it exists
    expected = output_path.with_suffix(".png")
    if expected.exists():
        return expected

    # Try with .png already in name
    alt = COVERS_DIR / f"{filename}.png"
    if alt.exists():
        return alt

    print(f"   Warning: image generation output not found at expected path.")
    print(f"   stdout: {result.stdout[:300]}")
    print(f"   stderr: {result.stderr[:300]}")
    return None


# ── Save generation record ────────────────────────────────────────────────────

def save_generation_record(brief: dict, author_name: str, refined_prompt: str, cover_path: Path | None):
    """Save a record of what was generated so it can be reproduced or iterated."""
    record = {
        "generated_at":   datetime.utcnow().isoformat(),
        "book_title":     brief.get("book_title", ""),
        "author_name":    author_name,
        "brief_version":  brief.get("brief_version", "v1"),
        "refined_prompt": refined_prompt,
        "cover_file":     str(cover_path) if cover_path else None,
        "color_palette":  brief.get("color_palette", {}),
        "typography":     brief.get("typography", {}),
        "status":         "success" if cover_path else "failed",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    record_path = OUTPUT_DIR / f"cover_generation_record_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    # Also update run_state with cover path
    state_path = MEMORY_DIR / "run_state.json"
    if state_path.exists():
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        state["cover_file"] = str(cover_path) if cover_path else None
        state["cover_generated_at"] = datetime.utcnow().isoformat()
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    return record_path


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    author_name: str,
    title: str | None = None,
    force: bool = False,
    variants: int = 1,
) -> dict:
    """
    Generate the final book cover image.

    Args:
        author_name: The author's name to include in generation record.
        title:       Book title to find the right cover brief.
        force:       Skip the publish gate (testing only).
        variants:    Number of cover variants to generate (1-3).

    Returns:
        dict with status, cover_path, prompt used.
    """
    print(f"\n{'='*60}")
    print(f"🖼  Cover Generator")
    print(f"{'='*60}")

    # ── Gate check
    allowed, reason = check_publish_gate(force)
    print(f"\n   Gate check: {'✅ PASSED' if allowed else '🔒 BLOCKED'}")
    print(f"   {reason}")

    if not allowed:
        return {"status": "blocked", "reason": reason}

    # ── Load brief
    brief = load_cover_brief(title)
    if not brief:
        print("\n   ⚠️  No cover brief found. Run cover_brief_agent.py first.")
        return {"status": "error", "reason": "No cover brief found."}

    print(f"\n   Book    : {brief.get('book_title', '')}")
    print(f"   Author  : {author_name}")
    print(f"   Concept : {brief.get('concept', {}).get('one_line_concept', '')}")

    # ── Refine prompt
    print(f"\n   Refining image prompt for KDP dimensions...")
    refined_prompt = refine_prompt_for_kdp(brief, author_name)
    print(f"   Prompt  : {refined_prompt[:120]}...")

    # ── Generate cover(s)
    generated = []
    date_str   = datetime.utcnow().strftime("%Y%m%d_%H%M")
    title_slug = (title or brief.get("book_title", "cover")).lower().replace(" ", "_")[:25]

    for i in range(1, variants + 1):
        filename = f"cover_{title_slug}_v{i}_{date_str}"
        print(f"\n   Generating variant {i}/{variants}: {filename}.png")

        cover_path = generate_cover_image(refined_prompt, filename)

        if cover_path:
            print(f"   ✅ Saved: {cover_path}")
            generated.append(str(cover_path))
        else:
            print(f"   ✗ Variant {i} failed.")

    # ── Save record
    record_path = save_generation_record(
        brief, author_name, refined_prompt,
        Path(generated[0]) if generated else None,
    )

    print(f"\n{'='*60}")
    if generated:
        print(f"✅ Cover generation complete")
        print(f"   Files     : {len(generated)} cover(s) in covers/")
        for g in generated:
            print(f"   → {g}")
        print(f"   Record    : {record_path}")
        print(f"\n   Next steps:")
        print(f"   1. Open the cover in Canva / Photoshop")
        print(f"   2. Add title text using the typography spec in the cover brief")
        print(f"   3. Add author name: {author_name}")
        print(f"   4. Export at 2560x1600px for ebook, 300 DPI PDF for paperback")
    else:
        print(f"✗ Cover generation failed — check covers/ directory")
    print(f"{'='*60}\n")

    return {
        "status":        "success" if generated else "failed",
        "covers":        generated,
        "prompt_used":   refined_prompt,
        "record":        str(record_path),
        "next_step":     "Add title text overlay in Canva or Photoshop",
    }


# ── Wire into orchestrator ────────────────────────────────────────────────────

def run_at_publish(author_name: str, title: str | None = None) -> dict:
    """
    Called by langgraph_orchestrator.py at the publish stage only.
    Wrapper that enforces the gate — never call with force=True from pipeline.
    """
    return run(author_name=author_name, title=title, force=False, variants=2)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cover Generator — publish stage only")
    parser.add_argument("--author",   required=True, help="Author name for the cover")
    parser.add_argument("--title",    default=None,  help="Book title (optional — uses latest brief)")
    parser.add_argument("--variants", type=int, default=2, help="Number of cover variants (default 2)")
    parser.add_argument("--force",    action="store_true", help="Skip publish gate (testing only)")
    args = parser.parse_args()

    result = run(
        author_name=args.author,
        title=args.title,
        force=args.force,
        variants=args.variants,
    )

    if result["status"] == "blocked":
        sys.exit(1)
