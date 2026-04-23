"""
Book Idea Generator Agent — V3 Core Pipeline
Reads all research findings and market data, then produces ranked book ideas
sorted by commercial opportunity, demand gap, and trend timing.

Runs automatically after research_agent.py completes.
Output: book-ideas/top_ideas_YYYYMMDD.json + book-ideas/top_ideas_YYYYMMDD.md

Standalone:  python book_idea_generator.py
"""

import json
import os
from pathlib import Path
from datetime import datetime
from config import get_client, DEFAULT_MODEL

client = get_client()

AGENTS_DIR   = Path(__file__).parent
MEMORY_DIR   = AGENTS_DIR / "memory"
RESEARCH_DIR = AGENTS_DIR.parent / "research"
IDEAS_DIR    = AGENTS_DIR.parent / "book-ideas"

# How many ranked ideas to generate
TOP_N = 5


def load_research_findings(limit: int = 30) -> list[dict]:
    """Load the most recent research findings from memory."""
    findings = []
    try:
        files = sorted(
            [f for f in os.listdir(MEMORY_DIR) if f.startswith("finding_") and f.endswith(".json")],
            reverse=True
        )[:limit]
        for fname in files:
            with open(MEMORY_DIR / fname) as f:
                data = json.load(f)
                if data.get("type") == "research_finding":
                    findings.append(data.get("data", {}))
    except Exception:
        pass
    return findings


def load_market_map() -> dict:
    market_path = MEMORY_DIR / "market_map.json"
    if market_path.exists():
        with open(market_path) as f:
            return json.load(f)
    return {}


def load_existing_ideas() -> list[str]:
    """Load titles of previously generated ideas to avoid recommending the same book twice."""
    existing = []
    try:
        for f in sorted(IDEAS_DIR.glob("top_ideas_*.json"), reverse=True)[:5]:
            with open(f) as fh:
                data = json.load(fh)
                for idea in data.get("ideas", []):
                    existing.append(idea.get("working_title", ""))
    except Exception:
        pass
    return existing


def generate_ideas(
    findings: list[dict],
    market_map: dict,
    existing_titles: list[str],
    n: int = TOP_N,
) -> dict:
    """
    Call the LLM to analyse research data and produce ranked book ideas.
    Returns structured JSON with top N ideas.
    """
    findings_text = json.dumps(findings, indent=2) if findings else "No findings available."
    market_text   = json.dumps(market_map, indent=2) if market_map else "No market map available."
    existing_text = "\n".join(f"- {t}" for t in existing_titles) if existing_titles else "None yet."

    system_prompt = """You are a senior KDP publishing strategist with a track record of
identifying book opportunities before they peak. You think like a data-driven publisher:
demand signals matter more than personal taste, timing matters more than perfection,
and a specific niche beats a broad topic every time.

Your job is to find the books that are most likely to reach top-20 in their Amazon
subcategory within 90 days of publication, based on the research data provided.
Output valid JSON only."""

    user_prompt = f"""Analyse the research data below and identify the top {n} book opportunities.

RESEARCH FINDINGS:
{findings_text}

MARKET MAP:
{market_text}

ALREADY RECOMMENDED (do not repeat these):
{existing_text}

For each idea, evaluate:
1. demand_gap: Is there clear search demand with insufficient supply?
2. competition_weakness: Are existing top books old, poorly reviewed, or narrowly positioned?
3. trend_timing: Is the trend emerging/growing (ideal) vs peak/declining (avoid)?
4. writing_feasibility: Can this be written authoritatively in 30,000–50,000 words?
5. commercial_clarity: Is the title/promise immediately understood by a browser?

Score each dimension 1–10. Compute an overall opportunity_score (weighted average).

Rank the ideas by opportunity_score descending.

Return this exact JSON:
{{
  "generated_at": "{datetime.utcnow().isoformat()}",
  "total_ideas": {n},
  "ideas": [
    {{
      "rank": 1,
      "working_title": "<draft title>",
      "subtitle_draft": "<subtitle — must name reader + outcome>",
      "one_line_pitch": "<what this book is in one sentence a stranger would understand>",
      "target_reader": "<precise description — age, situation, specific pain>",
      "core_promise": "<what the reader gains — specific, not vague>",
      "unique_angle": "<what makes this different from everything already on Amazon>",
      "scores": {{
        "demand_gap": <float 1-10>,
        "competition_weakness": <float 1-10>,
        "trend_timing": <float 1-10>,
        "writing_feasibility": <float 1-10>,
        "commercial_clarity": <float 1-10>
      }},
      "opportunity_score": <float 1-10>,
      "why_now": "<1-2 sentences on why this is the right moment>",
      "main_risk": "<the single biggest risk with this idea>",
      "estimated_chapter_count": <int>,
      "estimated_word_count": <int>,
      "comparable_books": ["<Title by Author>", ...],
      "primary_kdp_category": "<Books > Category > Subcategory>",
      "suggested_keywords": ["<keyword>", ...],
      "verdict": "<go|consider|monitor>"
    }}
  ],
  "top_recommendation": "<working_title of the #1 pick>",
  "strategist_note": "<2-3 sentence summary of the overall market picture and why the top pick wins>"
}}

Verdict rules:
- opportunity_score >= 8.0 → "go"
- opportunity_score 6.5–7.9 → "consider"
- opportunity_score < 6.5 → "monitor"

Be specific. Vague ideas ("a book about mindfulness") are worthless.
The best ideas have a razor-sharp reader, a specific pain, and a clear gap in the market."""

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=5000,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def save_ideas(result: dict) -> tuple[Path, Path]:
    """Save ranked ideas to both JSON and a readable Markdown report."""
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y%m%d_%H%M")

    # JSON
    json_path = IDEAS_DIR / f"top_ideas_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Markdown report
    md_path = IDEAS_DIR / f"top_ideas_{date_str}.md"
    lines = [
        f"# Book Idea Report — {datetime.utcnow().strftime('%d %B %Y')}",
        "",
        f"> **Top Pick:** {result.get('top_recommendation', '—')}",
        "",
        f"> {result.get('strategist_note', '')}",
        "",
        "---",
        "",
    ]

    for idea in result.get("ideas", []):
        verdict_icon = {"go": "🟢", "consider": "🟡", "monitor": "🔴"}.get(idea.get("verdict", ""), "⚪")
        lines += [
            f"## #{idea['rank']} — {idea['working_title']} {verdict_icon}",
            f"**{idea.get('subtitle_draft', '')}**",
            "",
            f"**Opportunity Score:** {idea.get('opportunity_score', '?'):.1f} / 10",
            "",
            "| Dimension | Score |",
            "|---|---|",
        ]
        for dim, score in idea.get("scores", {}).items():
            lines.append(f"| {dim.replace('_', ' ').title()} | {score:.1f} |")

        lines += [
            "",
            f"**One-line pitch:** {idea.get('one_line_pitch', '')}",
            "",
            f"**Target reader:** {idea.get('target_reader', '')}",
            "",
            f"**Core promise:** {idea.get('core_promise', '')}",
            "",
            f"**Unique angle:** {idea.get('unique_angle', '')}",
            "",
            f"**Why now:** {idea.get('why_now', '')}",
            "",
            f"**Main risk:** {idea.get('main_risk', '')}",
            "",
            f"**Est. length:** {idea.get('estimated_word_count', '?'):,} words · {idea.get('estimated_chapter_count', '?')} chapters",
            "",
            f"**KDP category:** {idea.get('primary_kdp_category', '')}",
            "",
            f"**Keywords:** {', '.join(idea.get('suggested_keywords', []))}",
            "",
            f"**Comparable books:** {', '.join(idea.get('comparable_books', []))}",
            "",
            "---",
            "",
        ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def print_summary(result: dict):
    """Print a clean terminal summary."""
    print(f"\n{'='*60}")
    print(f"📚 Book Idea Generator — {result.get('total_ideas', 0)} ideas ranked")
    print(f"{'='*60}")
    print(f"\n🏆 Top Pick: {result.get('top_recommendation', '—')}")
    print(f"\n{result.get('strategist_note', '')}\n")

    for idea in result.get("ideas", []):
        verdict_icon = {"go": "🟢", "consider": "🟡", "monitor": "🔴"}.get(idea.get("verdict", ""), "⚪")
        print(f"  #{idea['rank']} {verdict_icon}  {idea['working_title']}")
        print(f"      Score : {idea.get('opportunity_score', '?'):.1f}/10")
        print(f"      Pitch : {idea.get('one_line_pitch', '')}")
        print(f"      Reader: {idea.get('target_reader', '')}")
        print(f"      Why now: {idea.get('why_now', '')}")
        print()


def run(topic_hint: str = None, n: int = TOP_N) -> dict:
    """
    Main entry point. Called by langgraph_orchestrator.py and standalone.

    Args:
        topic_hint: Optional topic to bias ideas towards (e.g. "men's self-help").
        n: Number of ideas to generate.

    Returns:
        dict with ranked ideas.
    """
    print("\n📊 Book Idea Generator — loading research data...")

    findings    = load_research_findings()
    market_map  = load_market_map()
    existing    = load_existing_ideas()

    if not findings and not market_map:
        print("⚠️  No research data found. Run research_agent.py first.")
        print("   python research_agent.py")
        return {}

    print(f"   Loaded {len(findings)} findings + market map")
    print(f"   Generating top {n} ranked ideas...")

    # If topic hint given, inject it into market map
    if topic_hint:
        market_map["topic_hint"] = topic_hint

    result = generate_ideas(findings, market_map, existing, n=n)
    json_path, md_path = save_ideas(result)
    print_summary(result)

    print(f"   JSON  → {json_path}")
    print(f"   Report→ {md_path}")

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Book Idea Generator")
    parser.add_argument("--topic", default=None, help="Optional topic hint (e.g. 'men self-help')")
    parser.add_argument("--n",     type=int, default=TOP_N, help=f"Number of ideas to generate (default {TOP_N})")
    args = parser.parse_args()
    run(topic_hint=args.topic, n=args.n)
