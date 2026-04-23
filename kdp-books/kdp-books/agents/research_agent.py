"""
Research Agent — V3 Core Pipeline
Scans Amazon KDP market data, tracks category trends, identifies profitable niches,
and stores market intelligence for downstream agents.
Covers: category analysis, trend flagging, gap identification, competitor intel.
Run standalone:  python research_agent.py
"""

import anthropic
import json
import os
from datetime import datetime
from config import (ANTHROPIC_API_KEY, DEFAULT_MODEL, FAST_MODEL,
                    MEMORY_DIR, RESEARCH_DIR, TARGET_CATEGORIES)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a senior Amazon KDP market analyst with deep expertise in:
- Amazon's book ranking algorithm (BSR — Best Seller Rank)
- Category-level saturation vs. opportunity analysis
- Reader psychology and buying triggers
- Trend identification before peak saturation

Your research principles:
1. BSR under 100,000 = book is selling consistently
2. BSR under 10,000 = strong seller (50+ copies/month)
3. BSR under 1,000 = bestseller territory (500+ copies/month)
4. Competition sweet spot: < 1,000 competing titles for a keyword
5. Ideal category: top BSR #1 book ranks between 20,000–100,000
   (enough demand, not dominated by mega-publishers)

When analysing a category or topic, always report:
- Estimated monthly sales volume for top 10 books
- Review counts (proxy for market maturity)
- Price clustering (where readers expect to spend)
- Recency of top sellers (old = potentially stale or moated)
- Underserved sub-niches within the category
- Red flags (signs of saturation or algorithm suppression)

2025–2026 high-opportunity signals to watch for:
- AI productivity & the future of work
- Loneliness epidemic / social connection books
- Economic anxiety / recession prep / frugal living
- Late-diagnosed ADHD & neurodivergent adults
- Perimenopause & women's midlife reinvention
- Men's emotional health & masculinity redefined
- Side hustle & digital nomad evolution
- Faith + modern life tension (non-preachy spirituality)
- GenZ entering adulthood (first job, money, relationships)
- Regional demand gaps (UK, Australia, Canada underserved vs US)"""

RESEARCH_TOOLS = [
    {
        "name": "analyze_category",
        "description": "Deep-dives into a KDP category to find opportunity windows",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "subcategory": {"type": "string"},
                "bsr_range_top_10": {"type": "string", "description": "e.g. '5,000–80,000'"},
                "avg_review_count": {"type": "integer"},
                "avg_price": {"type": "number"},
                "saturation_level": {
                    "type": "string",
                    "enum": ["very_high", "high", "moderate", "low", "blue_ocean"]
                },
                "monthly_sales_estimate_top_book": {"type": "string"},
                "underserved_angles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific sub-niches or angles not well covered"
                },
                "opportunity_verdict": {"type": "string"},
                "recommended_entry_strategy": {"type": "string"},
            },
            "required": ["category", "bsr_range_top_10", "saturation_level",
                        "underserved_angles", "opportunity_verdict"]
        }
    },
    {
        "name": "flag_trend",
        "description": "Flags an emerging trend with actionable context",
        "input_schema": {
            "type": "object",
            "properties": {
                "trend_name": {"type": "string"},
                "trend_stage": {
                    "type": "string",
                    "enum": ["emerging", "growing", "peak", "declining"]
                },
                "evidence": {"type": "string"},
                "relevant_categories": {"type": "array", "items": {"type": "string"}},
                "book_opportunity": {"type": "string"},
                "urgency": {"type": "string", "enum": ["act_now", "within_3_months", "monitor"]},
                "estimated_window_months": {"type": "integer"},
            },
            "required": ["trend_name", "trend_stage", "evidence",
                        "book_opportunity", "urgency"]
        }
    },
    {
        "name": "identify_gap",
        "description": "Identifies a specific market gap — high search demand, low supply",
        "input_schema": {
            "type": "object",
            "properties": {
                "gap_description": {"type": "string"},
                "search_terms": {"type": "array", "items": {"type": "string"}},
                "why_gap_exists": {"type": "string"},
                "ideal_book_to_fill_it": {"type": "string"},
                "competition_count_estimate": {"type": "integer"},
                "confidence_level": {"type": "string", "enum": ["high", "medium", "speculative"]},
            },
            "required": ["gap_description", "search_terms", "ideal_book_to_fill_it", "confidence_level"]
        }
    },
    {
        "name": "save_finding",
        "description": "Persists a research finding to the shared memory store",
        "input_schema": {
            "type": "object",
            "properties": {
                "finding_type": {
                    "type": "string",
                    "enum": ["category_analysis", "trend", "gap", "competitor_intel", "pricing_data"]
                },
                "title": {"type": "string"},
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["finding_type", "title", "content", "priority"]
        }
    }
]


def save_finding(finding: dict) -> str:
    """Saves a research finding to both memory store and research directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"finding_{timestamp}.json"

    # Save to memory (shared with all agents)
    mem_path = os.path.join(MEMORY_DIR, filename)
    with open(mem_path, "w", encoding="utf-8") as f:
        json.dump({"type": "research_finding", "timestamp": timestamp, "data": finding}, f, indent=2)

    # Also save a readable report to research dir
    report_path = os.path.join(RESEARCH_DIR, f"report_{timestamp}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Research Finding: {finding.get('title', 'Untitled')}\n\n")
        f.write(f"**Type:** {finding.get('finding_type')}\n")
        f.write(f"**Priority:** {finding.get('priority')}\n")
        f.write(f"**Tags:** {', '.join(finding.get('tags', []))}\n\n")
        f.write(f"## Content\n\n{finding.get('content', '')}\n")

    return f"Saved: {finding.get('title')}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """Routes tool calls to their handlers."""
    if tool_name == "save_finding":
        return save_finding(tool_input)

    elif tool_name == "analyze_category":
        # Auto-save category analysis as a finding
        finding = {
            "finding_type": "category_analysis",
            "title": f"Category: {tool_input.get('category')} / {tool_input.get('subcategory', '')}",
            "content": json.dumps(tool_input, indent=2),
            "tags": ["category", tool_input.get("saturation_level", "")],
            "priority": "high" if tool_input.get("saturation_level") in ["low", "blue_ocean"] else "medium",
        }
        save_finding(finding)
        return json.dumps({"status": "analyzed", "category": tool_input["category"],
                          "saturation": tool_input["saturation_level"]})

    elif tool_name == "flag_trend":
        finding = {
            "finding_type": "trend",
            "title": f"Trend: {tool_input.get('trend_name')}",
            "content": json.dumps(tool_input, indent=2),
            "tags": ["trend", tool_input.get("trend_stage", ""), tool_input.get("urgency", "")],
            "priority": "high" if tool_input.get("urgency") == "act_now" else "medium",
        }
        save_finding(finding)
        return json.dumps({"status": "flagged", "trend": tool_input["trend_name"],
                          "urgency": tool_input["urgency"]})

    elif tool_name == "identify_gap":
        finding = {
            "finding_type": "gap",
            "title": f"Gap: {tool_input.get('gap_description', '')[:60]}",
            "content": json.dumps(tool_input, indent=2),
            "tags": ["gap", tool_input.get("confidence_level", "")],
            "priority": "high" if tool_input.get("confidence_level") == "high" else "medium",
        }
        save_finding(finding)
        return json.dumps({"status": "gap_identified", "confidence": tool_input["confidence_level"]})

    return json.dumps({"status": "unknown_tool"})


def run_research(topic: str = None, category: str = None) -> dict:
    """
    Main entry point. Runs a full or targeted research pass.
    - topic: specific subject to research (e.g. "ADHD productivity")
    - category: KDP category to deep-dive (e.g. "Self-Help")
    Returns dict with status and list of findings.
    """
    if topic:
        query = f"""Research the Amazon KDP market for the topic: "{topic}"
        Conduct the following analysis:
        1. analyze_category — find the most relevant KDP categories for this topic
        2. flag_trend — assess the trend stage (emerging / growing / peak / declining)
        3. identify_gap — find the specific underserved angle(s) within this topic
        4. save_finding — save a summary finding with actionable recommendations
        Be specific, data-driven, and commercial. Think like a publisher evaluating a $10,000 investment."""

    elif category:
        query = f"""Deep-dive the "{category}" category on Amazon KDP.
        Use analyze_category to assess:
        - BSR range of the top 10 books
        - Average review counts and prices
        - Saturation level and why
        - At least 5 underserved sub-niches with clear demand signals
        - Recommended entry strategy for a new publisher
        Then use identify_gap for the 2–3 most promising gaps found.
        Save all key findings with save_finding."""

    else:
        cats_sample = TARGET_CATEGORIES[:6]
        query = f"""Run a broad market scan across key Amazon KDP categories.
        Categories to cover: {json.dumps(cats_sample)}
        For each category:
        1. Use analyze_category — assess saturation and opportunity
        2. Flag any strong trends with flag_trend
        3. Identify the single best gap per category with identify_gap
        Focus on finding categories where a new publisher can realistically reach
        top 20 in their sub-category within 90 days with a quality book.
        Save all findings using save_finding.
        Prioritise specificity over breadth — better to deeply analyse 3 categories
        than superficially skim 10."""

    messages = [{"role": "user", "content": query}]
    findings_text = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=RESEARCH_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    findings_text.append({"content": block.text})
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

    return {"status": "complete", "findings": findings_text}


def load_all_findings(limit: int = 20) -> list:
    """
    Loads the most recent research findings from the memory store.
    Used by downstream agents to get context without re-running research.
    """
    findings = []
    try:
        files = sorted(
            [f for f in os.listdir(MEMORY_DIR) if f.endswith(".json")],
            reverse=True
        )[:limit]
        for fname in files:
            with open(os.path.join(MEMORY_DIR, fname)) as f:
                data = json.load(f)
                if data.get("type") == "research_finding":
                    findings.append(data.get("data", {}))
    except Exception:
        pass
    return findings


def build_market_map(book_brief: dict) -> dict:
    """
    Run targeted market research from the book brief and save to memory/market_map.json.
    Called by langgraph_orchestrator.py at step 5.
    """
    import json as _json
    from pathlib import Path

    topic = book_brief.get("topic_normalized") or book_brief.get("book_thesis", "")
    comparables = book_brief.get("comparable_books", [])

    print(f"\n🔬 Research Agent — Building market map for: {topic}")
    result = run_research(topic=topic)

    market_map = {
        "topic": topic,
        "comparable_books": comparables,
        "findings": result.get("findings", []),
        "raw_findings": load_all_findings(limit=10),
    }

    memory_dir = Path(__file__).parent / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    with open(memory_dir / "market_map.json", "w", encoding="utf-8") as f:
        _json.dump(market_map, f, indent=2)

    print(f"   Market map saved to memory/market_map.json")
    return market_map


if __name__ == "__main__":
    print("=== KDP Research Agent ===")
    print("\n[1/3] Full category scan...")
    result = run_research()
    for f in result["findings"]:
        print(f["content"])

    print("\n[2/3] Trend deep-dive: ADHD productivity...")
    run_research(topic="ADHD productivity adults")

    print("\n[3/3] Category deep-dive: Self-Help...")
    run_research(category="Self-Help")

    print(f"\nDone. Findings saved to: {MEMORY_DIR}")
    print(f"Reports saved to: {RESEARCH_DIR}")
