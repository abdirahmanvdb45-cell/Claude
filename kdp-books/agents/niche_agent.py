"""
AGENT 2: Niche Discovery Agent
Finds profitable, underserved niches by analyzing reader complaints,
emotional gaps, cultural trends, and regional demand signals.

Run standalone:  python niche_agent.py
"""

import anthropic
import json
import os
from datetime import datetime
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MEMORY_DIR, DESIRE_CLUSTERS
from research_agent import load_all_findings

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a niche discovery specialist for Amazon KDP publishing.

You identify profitable gaps in the book market by:
1. Analyzing what readers complain about in existing book reviews
2. Mapping unmet emotional and practical needs to specific demographics
3. Identifying cultural trends that create new demand before supply catches up
4. Spotting regional demand variations (US vs UK vs Canada vs Australia)
5. Finding the intersection of HIGH DESIRE + LOW SUPPLY = opportunity

Your output always includes:
- A specific niche name (not generic — be exact)
- The reader demographic (age, gender, life situation)
- The core unmet need (what they want but can't find)
- The emotional driver (what feeling would the ideal book give them)
- Competition assessment (overcrowded / moderate / blue ocean)
- Opportunity score (1–10)
- A specific book concept that fills the gap

You think in terms of HUMAN DESIRES first, book topics second.
A man who wants to be more attractive to women doesn't search "dating advice" —
he searches for confidence, status, charisma, presence. Speak to the desire, not the category."""

NICHE_TOOLS = [
    {
        "name": "score_niche",
        "description": "Evaluates and scores a niche opportunity",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_name": {"type": "string"},
                "target_demographic": {"type": "string"},
                "unmet_need": {"type": "string"},
                "emotional_driver": {"type": "string"},
                "desire_cluster": {
                    "type": "string",
                    "enum": ["survival", "status", "love", "identity", "health", "growth", "freedom"]
                },
                "competition_level": {"type": "string", "enum": ["overcrowded", "moderate", "low", "blue_ocean"]},
                "opportunity_score": {"type": "integer"},
                "regions_with_highest_demand": {"type": "array", "items": {"type": "string"}},
                "book_concept": {"type": "string"},
                "suggested_title": {"type": "string"},
            },
            "required": ["niche_name", "target_demographic", "unmet_need", "emotional_driver",
                        "desire_cluster", "competition_level", "opportunity_score", "book_concept", "suggested_title"]
        }
    },
    {
        "name": "map_desire_to_niche",
        "description": "Maps a fundamental human desire to concrete book niche opportunities",
        "input_schema": {
            "type": "object",
            "properties": {
                "desire": {"type": "string"},
                "demographic": {"type": "string"},
                "current_books_failing_because": {"type": "string"},
                "opportunity": {"type": "string"},
            },
            "required": ["desire", "demographic", "current_books_failing_because", "opportunity"]
        }
    },
    {
        "name": "save_niche",
        "description": "Saves a validated niche opportunity to memory",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_data": {"type": "object"},
            },
            "required": ["niche_data"]
        }
    }
]


def save_niche(niche_data: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"niche_{timestamp}.json"
    filepath = os.path.join(MEMORY_DIR, filename)
    with open(filepath, "w") as f:
        json.dump({"type": "niche_opportunity", "timestamp": timestamp, "data": niche_data}, f, indent=2)
    return f"Niche saved: {niche_data.get('niche_name', 'unnamed')}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "save_niche":
        return save_niche(tool_input["niche_data"])
    elif tool_name == "score_niche":
        save_niche(tool_input)
        return json.dumps({"status": "scored_and_saved", "niche": tool_input["niche_name"],
                          "score": tool_input["opportunity_score"]})
    elif tool_name == "map_desire_to_niche":
        return json.dumps({"status": "mapped", "desire": tool_input["desire"]})
    return json.dumps({"status": "unknown_tool"})


def discover_niches(focus: str = None, gender: str = None, age_group: str = None) -> dict:
    """
    Main entry point. Discovers and scores niche opportunities.
    Can be focused by topic, gender, or age group.
    """
    # Load context from research agent if available
    existing_findings = load_all_findings()
    context = ""
    if existing_findings:
        context = f"\n\nContext from Research Agent:\n{json.dumps(existing_findings[:5], indent=2)}"

    if focus:
        query = f"""Find the top 5 underserved niche opportunities within: {focus}

        For each niche:
        1. Name it precisely (not generic)
        2. Define exactly who is underserved (demographic + life situation)
        3. Identify what they desperately want but can't find in existing books
        4. Name the core emotional driver (what feeling would the perfect book give them?)
        5. Assess competition level honestly
        6. Score the opportunity 1–10
        7. Propose a specific book concept with a working title

        Use score_niche tool for each opportunity found.{context}"""

    elif gender and age_group:
        desire_examples = list(DESIRE_CLUSTERS.get("status", []))[:3]
        query = f"""Analyze book buying desires for {gender}s aged {age_group}.

        Map their deepest desires to book opportunities:
        - What do they want more than anything? (money, love, status, health, purpose, freedom?)
        - Which of these desires is currently LEAST served by books on Amazon?
        - What would a book look like that speaks directly to this desire?
        - What title would make them stop scrolling and click immediately?

        Example desire signals to consider: {', '.join(desire_examples)}

        Use map_desire_to_niche and score_niche tools for each opportunity.{context}"""

    else:
        query = f"""Run a full niche discovery scan across all desire clusters.

        Desire clusters to analyze: {json.dumps(DESIRE_CLUSTERS, indent=2)}

        For each cluster, find:
        1. The #1 underserved demographic (who is most ignored by existing books?)
        2. Their specific unfulfilled desire
        3. A book concept that would feel like it was written JUST for them

        Priority order: survival → status → love → identity → health → growth → freedom

        Score each niche using the score_niche tool.
        Aim to identify at least 10 high-opportunity niches.{context}"""

    messages = [{"role": "user", "content": query}]
    niches = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=NICHE_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    niches.append(block.text)
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

    return {"status": "complete", "niches": niches}


def get_top_niches(min_score: int = 7) -> list:
    """Returns all saved niches with opportunity score >= min_score."""
    top = []
    for fname in os.listdir(MEMORY_DIR):
        if "niche" in fname and fname.endswith(".json"):
            with open(os.path.join(MEMORY_DIR, fname)) as f:
                data = json.load(f)
                score = data.get("data", {}).get("opportunity_score", 0)
                if score >= min_score:
                    top.append(data)
    return sorted(top, key=lambda x: x.get("data", {}).get("opportunity_score", 0), reverse=True)


if __name__ == "__main__":
    print("=== KDP Niche Discovery Agent ===")

    # Full scan
    print("\n[1/3] Running full desire-cluster scan...")
    result = discover_niches()

    # Gender-specific scans
    print("\n[2/3] Scanning male desire niches (25–40)...")
    discover_niches(gender="male", age_group="25-40")

    print("\n[3/3] Scanning female desire niches (28–50)...")
    discover_niches(gender="female", age_group="28-50")

    print("\n--- Top Opportunities Found ---")
    top = get_top_niches(min_score=7)
    for n in top:
        d = n.get("data", {})
        print(f"\n[Score {d.get('opportunity_score')}/10] {d.get('niche_name')}")
        print(f"  Target: {d.get('target_demographic')}")
        print(f"  Book: {d.get('suggested_title')}")
