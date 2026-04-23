"""
Commercial Readiness Evaluator Agent — V2
Judges whether the manuscript and its packaging are commercially legible
and positioned to actually sell on KDP or any retail channel.
"""

import json
from pathlib import Path
from config import get_client, DEFAULT_MODEL

client = get_client()


def evaluate_commercial_readiness(
    book_brief: dict,
    manuscript_summary: str,
    subtitle_options: list[str] | None = None,
    packaging_copy: str = "",
    market_map: dict | None = None,
) -> dict:
    """
    Evaluate whether the book is commercially ready to publish.

    Args:
        book_brief: The locked book brief dict.
        manuscript_summary: Short summary of the completed manuscript.
        subtitle_options: List of subtitle candidates to evaluate.
        packaging_copy: Back cover / KDP description copy draft.
        market_map: Market research dict.

    Returns:
        dict with scores, weaknesses, packaging risks, rewrite targets, go/no-go
    """
    subtitles_text = "\n".join(f"- {s}" for s in (subtitle_options or []))
    market_text = json.dumps(market_map, indent=2) if market_map else "Not provided."

    system_prompt = """You are the Commercial Readiness Evaluator. You judge whether a nonfiction
book is ready for market — not just whether it's well-written, but whether it can be found,
understood, and bought by the target reader. You think like a publisher, a KDP optimizer,
and a reader scrolling past a thumbnail. Output valid JSON only."""

    user_prompt = f"""Evaluate this book's commercial readiness.

BOOK BRIEF:
{json.dumps(book_brief, indent=2)}

MANUSCRIPT SUMMARY:
{manuscript_summary}

SUBTITLE OPTIONS:
{subtitles_text or "None provided."}

PACKAGING COPY (back cover / KDP description):
{packaging_copy or "Not provided."}

MARKET MAP:
{market_text}

Evaluate each dimension honestly:

1. title_clarity (1-10): Does the title immediately communicate the book's value?
2. subtitle_specificity (1-10): Does the subtitle name the exact reader and result?
3. audience_fit (1-10): Is the reader avatar sharp enough to create a "this is for me" reaction?
4. promise_strength (1-10): Is the core promise bold, specific, and believable?
5. market_distinction (1-10): Is there a clear reason to choose this over competitors?
6. practical_sellability (1-10): Can this book be summarised in one sentence a stranger would understand?
7. kdp_search_visibility (1-10): Does the title/subtitle contain words buyers actually search?
8. cover_copy_quality (1-10): Does the packaging copy convert browsers to buyers?

Return this JSON:
{{
  "scores": {{
    "title_clarity": <float>,
    "subtitle_specificity": <float>,
    "audience_fit": <float>,
    "promise_strength": <float>,
    "market_distinction": <float>,
    "practical_sellability": <float>,
    "kdp_search_visibility": <float>,
    "cover_copy_quality": <float>
  }},
  "overall_commercial_score": <float 1-10>,
  "core_weaknesses": ["<weakness>", ...],
  "packaging_risks": ["<risk>", ...],
  "rewrite_targets": [
    {{
      "element": "<title|subtitle|description|promise>",
      "current_problem": "<what's wrong>",
      "rewrite_instruction": "<what to do>",
      "example_direction": "<optional brief example>"
    }}
  ],
  "best_subtitle_option": "<chosen subtitle or null>",
  "subtitle_rationale": "<why>",
  "go_to_packaging": <bool>,
  "evaluator_verdict": "<two sentence overall assessment>"
}}

Decision rule:
- overall_commercial_score >= 7.5 → go_to_packaging = true
- overall_commercial_score < 7.5 → go_to_packaging = false, return rewrite targets"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    # Save report
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "commercial_readiness.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n💰 Commercial Readiness Evaluator")
    print(f"   Overall Score  : {result.get('overall_commercial_score', '?'):.1f} / 10")
    print(f"   Go to Market   : {'YES' if result.get('go_to_packaging') else 'NO — revisions needed'}")
    if result.get("core_weaknesses"):
        print("   Core Weaknesses:")
        for w in result["core_weaknesses"]:
            print(f"     • {w}")
    print(f"   Verdict: {result.get('evaluator_verdict', '')}")

    return result


def generate_kdp_listing(book_brief: dict, commercial_report: dict) -> dict:
    """
    Generate a complete, KDP-optimised listing package:
    title, subtitle, description, backend keywords, and category selections.
    Previously handled by the removed optimization_agent.py.

    Args:
        book_brief: The approved book brief.
        commercial_report: Output from evaluate_commercial_readiness().

    Returns:
        dict with all listing assets. Saved to output/kdp_listing.json.
    """
    system_prompt = """You are a KDP listing specialist. You write titles, subtitles,
descriptions, and keyword strings that rank on Amazon and convert browsers into buyers.
You think like a reader typing into the search bar, not like a writer describing their book.
Output valid JSON only."""

    rewrite_targets = commercial_report.get("rewrite_targets", [])
    best_subtitle = commercial_report.get("best_subtitle_option", "")

    user_prompt = f"""Create a complete KDP listing package for this book.

BOOK BRIEF:
{json.dumps(book_brief, indent=2)}

COMMERCIAL REPORT — known weaknesses to address:
{json.dumps(rewrite_targets, indent=2)}

BEST SUBTITLE IDENTIFIED: {best_subtitle or 'not yet determined'}

Generate:
1. Final title (max 60 characters)
2. Final subtitle (max 255 characters — must name reader + outcome)
3. KDP description (600–800 words — HTML formatted with <b>, <br>)
4. 7 backend keyword strings (each max 50 characters, no title/author words)
5. Primary category (exact Amazon path)
6. Secondary category (exact Amazon path)
7. A/B test subtitle option (alternative to test against)

Return this JSON:
{{
  "title": "<final title>",
  "subtitle": "<final subtitle>",
  "description_html": "<KDP HTML description>",
  "backend_keywords": ["<keyword string 1>", ..., "<keyword string 7>"],
  "primary_category": "<Books > Category > Subcategory>",
  "secondary_category": "<Books > Category > Subcategory>",
  "ab_test_subtitle": "<alternative subtitle>",
  "pricing_recommendation": "<ebook price and paperback price>",
  "listing_notes": "<any important considerations>"
}}"""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "kdp_listing.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\n📌 KDP Listing Generated")
    print(f"   Title    : {result.get('title', '')}")
    print(f"   Subtitle : {result.get('subtitle', '')}")
    print(f"   Category : {result.get('primary_category', '')}")
    print(f"   Keywords : {len(result.get('backend_keywords', []))} strings")

    return result


if __name__ == "__main__":
    brief = {
        "working_title": "The Man She Stays For",
        "subtitle_options": [
            "What Women Actually Respond To — And Why Most Men Never Figure It Out",
            "How to Behave Like the Man Women Choose Long-Term",
        ],
        "reader_avatar": "Men aged 22–45 who keep getting the same results with women",
        "core_promise": "Understand what women actually respond to and change your behaviour accordingly",
        "book_thesis": "Most men fail with women not because of what they say, but because of how they carry themselves",
    }
    result = evaluate_commercial_readiness(
        book_brief=brief,
        manuscript_summary="A 10-chapter nonfiction guide covering presence, testing signals, nice-guy traps, listening, decisiveness, emotional strength, neediness, public behaviour, conflict handling, and long-term retention.",
        subtitle_options=brief["subtitle_options"],
    )
    print(json.dumps(result, indent=2))
