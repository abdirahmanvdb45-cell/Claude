"""
AGENT 3: Psychology Agent
Translates human desires into compelling book concepts.
Defines psychological hooks, transformation promises, and
emotional triggers that convert browsers into buyers.
"""

import anthropic
import json
import os
from datetime import datetime
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MEMORY_DIR, BOOK_IDEAS_DIR
from research_agent import load_all_findings

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a behavioral psychologist and publishing strategist who specializes in
understanding why people buy books and what makes them feel compelled to read.

You operate on the principle that people don't buy books — they buy versions of themselves.
They buy the future self the book promises to unlock.

Your expertise:
- Maslow's hierarchy as applied to publishing (survival → belonging → esteem → self-actualization)
- Cialdini's influence principles in book marketing (social proof, scarcity, authority, liking)
- The Emotional Journey Map: current pain → awareness → hope → belief → action
- Gender psychology in reading behavior
- Age-cohort reading motivations (Gen Z vs Millennial vs Gen X vs Boomer)
- The 7 deadly emotions that drive book purchases:
  1. SHAME (fear of not being enough)
  2. FEAR (loss, failure, being alone)
  3. DESIRE (money, love, status, beauty)
  4. ENVY (wanting what others have)
  5. HOPE (belief in transformation)
  6. ANGER (injustice, being misunderstood)
  7. LONELINESS (wanting to feel seen)

Every book concept you generate must:
- Name the exact emotion driving the purchase
- State the transformation promise clearly (from X to Y)
- Identify the moment of purchase (what triggers someone to search and buy?)
- Define the identity the reader wants to inhabit after reading
- Include a psychologically charged title that makes the reader feel "this is for ME"

You think like a master copywriter, not an academic. Results, not jargon."""

PSYCHOLOGY_TOOLS = [
    {
        "name": "build_book_concept",
        "description": "Builds a complete psychologically-engineered book concept",
        "input_schema": {
            "type": "object",
            "properties": {
                "working_title": {"type": "string"},
                "subtitle": {"type": "string"},
                "primary_emotion": {
                    "type": "string",
                    "enum": ["shame", "fear", "desire", "envy", "hope", "anger", "loneliness"]
                },
                "transformation_promise": {"type": "string", "description": "From X (current pain) to Y (desired outcome)"},
                "target_reader_identity": {"type": "string", "description": "Who the reader sees themselves as NOW"},
                "aspirational_reader_identity": {"type": "string", "description": "Who they want to become"},
                "purchase_trigger_moment": {"type": "string", "description": "The specific life moment that makes someone search for this book"},
                "hook_sentence": {"type": "string", "description": "One sentence that would make the target reader stop scrolling"},
                "chapter_arc": {"type": "array", "items": {"type": "string"}, "description": "High-level emotional journey through the book"},
                "competing_identity": {"type": "string", "description": "What existing books get wrong about this reader"},
                "gender_primary": {"type": "string", "enum": ["male", "female", "both"]},
                "age_range": {"type": "string"},
                "desire_cluster": {"type": "string"},
            },
            "required": ["working_title", "subtitle", "primary_emotion", "transformation_promise",
                        "target_reader_identity", "aspirational_reader_identity", "purchase_trigger_moment",
                        "hook_sentence", "gender_primary", "age_range", "desire_cluster"]
        }
    },
    {
        "name": "analyze_emotional_trigger",
        "description": "Analyzes which emotional trigger would be most effective for a given audience",
        "input_schema": {
            "type": "object",
            "properties": {
                "audience": {"type": "string"},
                "primary_trigger": {"type": "string"},
                "secondary_trigger": {"type": "string"},
                "title_formula": {"type": "string"},
                "why_this_works": {"type": "string"},
            },
            "required": ["audience", "primary_trigger", "secondary_trigger", "title_formula", "why_this_works"]
        }
    },
    {
        "name": "save_concept",
        "description": "Saves a book concept to the ideas library",
        "input_schema": {
            "type": "object",
            "properties": {
                "concept": {"type": "object"},
            },
            "required": ["concept"]
        }
    }
]


def save_concept(concept: dict) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title_slug = concept.get("working_title", "concept").lower().replace(" ", "_")[:30]
    filename = f"{title_slug}_{timestamp}.json"
    filepath = os.path.join(BOOK_IDEAS_DIR, filename)
    with open(filepath, "w") as f:
        json.dump({"type": "book_concept", "timestamp": timestamp, "data": concept}, f, indent=2)
    return f"Concept saved: {concept.get('working_title')}"


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "save_concept":
        return save_concept(tool_input["concept"])
    elif tool_name == "build_book_concept":
        save_concept(tool_input)
        return json.dumps({"status": "concept_built", "title": tool_input["working_title"]})
    elif tool_name == "analyze_emotional_trigger":
        return json.dumps({"status": "trigger_analyzed", "audience": tool_input["audience"]})
    return json.dumps({"status": "unknown_tool"})


def generate_concepts(niche: str = None, demographic: str = None,
                      desire: str = None, n_concepts: int = 5) -> dict:
    """
    Generates psychologically-engineered book concepts.
    Can target a specific niche, demographic, or desire cluster.
    """
    context_findings = load_all_findings()
    context = ""
    if context_findings:
        niche_findings = [f for f in context_findings if f.get("type") == "niche_opportunity"]
        if niche_findings:
            context = f"\n\nNiches identified by Niche Discovery Agent:\n{json.dumps(niche_findings[:3], indent=2)}"

    if niche and demographic:
        query = f"""Generate {n_concepts} psychologically-engineered book concepts for:
        Niche: {niche}
        Demographic: {demographic}

        For each concept:
        1. Start with the EMOTION — what is this person feeling when they search for a book?
        2. Define the transformation promise precisely
        3. Identify the exact moment in life that triggers the purchase
        4. Create a title that makes them feel "this was written for me"
        5. Outline the emotional journey through the book (not just chapter topics)

        Use build_book_concept tool for each concept generated.{context}"""

    elif desire:
        query = f"""Map the desire "{desire}" to {n_concepts} book concepts across different demographics.

        The desire: {desire}

        Show how this same desire manifests differently for:
        - Men vs Women
        - Different age cohorts
        - Different life situations (single, married, divorced, parent, career person)

        For each manifestation, build a distinct book concept using build_book_concept tool.
        Make each concept feel completely different even though they target the same desire.{context}"""

    else:
        query = f"""Generate {n_concepts} high-conversion book concepts based on the 7 core purchase emotions.

        Cover at least one concept from each:
        - SHAME-driven (fear of not being enough)
        - FEAR-driven (losing something important)
        - DESIRE-driven (getting something badly wanted)
        - HOPE-driven (belief in possible transformation)
        - LONELINESS-driven (wanting to feel seen and understood)

        For each, use build_book_concept to create a fully psychologically-engineered concept.
        Prioritize concepts where the reader would feel the book is SPECIFICALLY for them.{context}"""

    messages = [{"role": "user", "content": query}]
    output = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=PSYCHOLOGY_TOOLS,
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

    return {"status": "complete", "concepts": output}


def analyze_bestseller_psychology(title: str, description: str) -> dict:
    """
    Analyzes why a specific bestselling book works psychologically.
    Useful for reverse-engineering what makes top books sell.
    """
    query = f"""Psychologically dissect this bestselling book:

    Title: {title}
    Description: {description}

    Explain:
    1. Which of the 7 core purchase emotions does this title trigger first?
    2. What is the exact transformation promise (stated or implied)?
    3. What life moment makes someone buy this? (be specific)
    4. What identity is the reader trying to escape?
    5. What identity are they trying to claim?
    6. What does the cover likely signal about the brand promise?
    7. Why do readers leave 5-star reviews? (what transformation did they feel?)
    8. What would a competing book need to do differently to steal market share?

    Use analyze_emotional_trigger to structure your findings."""

    messages = [{"role": "user", "content": query}]
    output = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=PSYCHOLOGY_TOOLS,
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

    return {"status": "complete", "analysis": output}


if __name__ == "__main__":
    print("=== KDP Psychology Agent ===")

    print("\n[1/2] Generating desire-mapped concepts...")
    result = generate_concepts(n_concepts=5)
    for c in result["concepts"]:
        print(c)

    print("\n[2/2] Analyzing example bestseller psychology...")
    analysis = analyze_bestseller_psychology(
        "Atomic Habits",
        "An Easy & Proven Way to Build Good Habits & Break Bad Ones"
    )
    for a in analysis["analysis"]:
        print(a)
