"""
AGENT 1: Research Agent
Continuously monitors Amazon KDP bestseller data, tracks trends,
identifies new opportunities, and stores findings to memory.

Run standalone:  python research_agent.py
Run via orchestrator: imported by automation_agent.py
"""

import anthropic
import json
import os
from datetime import datetime
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MEMORY_DIR, TARGET_CATEGORIES

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an elite Amazon KDP market research specialist with deep knowledge of:
- Amazon bestseller ranking systems (BSR) and what drives rankings
- Kindle Unlimited (KU) page-read economics
- Category and keyword dynamics on Amazon
- Publishing industry trends and cultural shifts
- Reader psychology and purchase behavior

Your job is to analyze book market data and return structured, actionable intelligence.
Always return JSON-formatted responses when asked for structured data.
Be specific — cite real book titles, real authors, real data points wherever possible.
Never be generic. Every insight must be tied to a specific, observable market signal."""

RESEARCH_TOOLS = [
    {
        "name": "analyze_bestseller_data",
        "description": "Analyzes a bestseller list and extracts structured intelligence for each book",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "The Amazon category being analyzed"},
                "books": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer"},
                            "title": {"type": "string"},
                            "author": {"type": "string"},
                            "summary": {"type": "string"},
                        }
                    }
                }
            },
            "required": ["category", "books"]
        }
    },
    {
        "name": "identify_trend",
        "description": "Flags a new or accelerating market trend with supporting evidence",
        "input_schema": {
            "type": "object",
            "properties": {
                "trend_name": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "opportunity_score": {"type": "integer", "description": "1-10, how actionable this is for a new author"},
                "recommended_action": {"type": "string"},
            },
            "required": ["trend_name", "evidence", "opportunity_score", "recommended_action"]
        }
    },
    {
        "name": "save_finding",
        "description": "Saves a research finding to the memory store for use by other agents",
        "input_schema": {
            "type": "object",
            "properties": {
                "finding_type": {"type": "string", "enum": ["bestseller", "trend", "niche_opportunity", "gap"]},
                "data": {"type": "object"},
            },
            "required": ["finding_type", "data"]
        }
    }
]


def save_finding(finding_type: str, data: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{finding_type}_{timestamp}.json"
    filepath = os.path.join(MEMORY_DIR, filename)
    payload = {"type": finding_type, "timestamp": timestamp, "data": data}
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)
    return f"Saved to {filepath}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "save_finding":
        return save_finding(tool_input["finding_type"], tool_input["data"])
    elif tool_name == "analyze_bestseller_data":
        return json.dumps({"status": "analyzed", "category": tool_input["category"], "count": len(tool_input.get("books", []))})
    elif tool_name == "identify_trend":
        save_finding("trend", tool_input)
        return json.dumps({"status": "trend_logged", "name": tool_input["trend_name"]})
    return json.dumps({"status": "unknown_tool"})


def run_research(topic: str = None, category: str = None) -> dict:
    """
    Main entry point. Runs a research cycle on a given topic or category.
    Returns structured findings dict.
    """
    if topic:
        query = f"""Research this KDP market topic in depth: {topic}

        Return structured analysis covering:
        1. Top 10 books currently dominating this space (title, author, why they sell)
        2. The core emotional hook that makes readers buy in this space
        3. What readers are NOT getting from existing books (the gap)
        4. A concrete book opportunity with title concept, target audience, and positioning
        5. Recommended price point and category placement on Amazon KDP

        Use your save_finding tool to store any high-value opportunities you identify."""

    elif category:
        query = f"""Analyze the Amazon KDP '{category}' category.

        Identify:
        1. The current #1–5 bestsellers and why they dominate
        2. The reader psychology driving purchases in this category
        3. Any emerging sub-niches with growing demand but low supply
        4. What a new author would need to do to break into this category's top 20
        5. Specific keyword opportunities (high search, lower competition)

        Save all opportunities using your save_finding tool."""

    else:
        query = """Run a full-spectrum KDP market scan.

        Cover these categories: Self-Help, Romance, Thriller, Personal Finance, Health & Wellness.
        For each, identify:
        - The dominant book (and why it's winning)
        - One underserved niche inside the category
        - One actionable book idea for a new author

        Save all findings using your save_finding tool."""

    messages = [{"role": "user", "content": query}]
    findings = []

    # Agentic loop with tool use
    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=RESEARCH_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract final text response
            for block in response.content:
                if hasattr(block, "text"):
                    findings.append({"type": "analysis", "content": block.text})
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

    return {"status": "complete", "findings": findings}


def load_all_findings() -> list:
    """Load all saved findings from memory for other agents to consume."""
    findings = []
    for fname in os.listdir(MEMORY_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(MEMORY_DIR, fname)) as f:
                findings.append(json.load(f))
    return findings


if __name__ == "__main__":
    print("=== KDP Research Agent ===")
    print("Running full market scan...")
    result = run_research()
    print("\n--- Research Complete ---")
    for finding in result["findings"]:
        print(finding["content"])
