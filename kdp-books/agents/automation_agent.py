"""
AGENT 6: Automation Agent (Orchestrator)
The master agent that coordinates all other agents.
Runs the full pipeline from market research → niche → concept → book → listing.
Can operate autonomously, asking targeted questions only when required.

Run:  python automation_agent.py
"""

import anthropic
import json
import os
import time
from datetime import datetime
from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, FAST_MODEL, MEMORY_DIR, BOOK_IDEAS_DIR

# Import all sub-agents
from research_agent import run_research, load_all_findings
from niche_agent import discover_niches, get_top_niches
from psychology_agent import generate_concepts, analyze_bestseller_psychology
from writing_agent import create_outline, write_chapter, compile_manuscript
from optimization_agent import optimize_book

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are the Automation Agent — the master orchestrator of a KDP publishing system.

You coordinate 5 specialized agents:
1. Research Agent — scans Amazon KDP markets continuously
2. Niche Discovery Agent — finds underserved opportunities
3. Psychology Agent — builds psychologically-engineered book concepts
4. Writing Agent — writes full manuscripts chapter by chapter
5. Optimization Agent — creates KDP listings (title, keywords, description, categories)

Your operating principles:
- THINK BEFORE ACTING: assess what information you have vs. what you need
- MINIMIZE INTERRUPTIONS: only ask the human a question when absolutely necessary
- BE DECISIVE: when multiple paths are valid, choose the best one and proceed
- TRACK PROGRESS: know exactly where you are in the pipeline at all times
- QUALITY GATE: don't proceed to the next phase until the current one is complete

Pipeline flow:
Research → Niche Discovery → Psychology/Concept → Outline → Write Chapters → Optimize → Report

You should ask the user ONLY these types of questions:
1. Which book idea to prioritize (when multiple strong options exist)
2. Personal details that improve the book (their experience, story, preferences)
3. Go/no-go decisions on major pivots
4. API keys or tool access needed to proceed

Everything else: decide and do."""

ORCHESTRATOR_TOOLS = [
    {
        "name": "run_pipeline_phase",
        "description": "Executes a specific phase of the publishing pipeline",
        "input_schema": {
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "enum": ["research", "niche_discovery", "concept_generation",
                            "outline", "write_chapter", "optimize", "compile"]
                },
                "parameters": {"type": "object"},
            },
            "required": ["phase", "parameters"]
        }
    },
    {
        "name": "check_pipeline_status",
        "description": "Reports on what has been completed and what's next",
        "input_schema": {
            "type": "object",
            "properties": {
                "current_phase": {"type": "string"},
                "completed": {"type": "array", "items": {"type": "string"}},
                "pending": {"type": "array", "items": {"type": "string"}},
                "blockers": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
            },
            "required": ["current_phase", "completed", "pending", "recommendation"]
        }
    },
    {
        "name": "ask_user",
        "description": "Asks the user a targeted question when human input is genuinely required",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "context": {"type": "string", "description": "Why this question is necessary"},
                "options": {"type": "array", "items": {"type": "string"}, "description": "Specific options if applicable"},
            },
            "required": ["question", "context"]
        }
    },
    {
        "name": "select_book_to_write",
        "description": "Selects the highest-opportunity book to write next based on all available data",
        "input_schema": {
            "type": "object",
            "properties": {
                "selected_book": {"type": "string"},
                "rationale": {"type": "string"},
                "estimated_earnings_monthly": {"type": "string"},
                "time_to_publish": {"type": "string"},
            },
            "required": ["selected_book", "rationale"]
        }
    }
]


def execute_phase(phase: str, parameters: dict) -> dict:
    """Routes pipeline phases to the correct sub-agent."""
    print(f"\n  [Pipeline] Executing: {phase}")

    if phase == "research":
        topic = parameters.get("topic")
        category = parameters.get("category")
        return run_research(topic=topic, category=category)

    elif phase == "niche_discovery":
        focus = parameters.get("focus")
        gender = parameters.get("gender")
        age_group = parameters.get("age_group")
        return discover_niches(focus=focus, gender=gender, age_group=age_group)

    elif phase == "concept_generation":
        niche = parameters.get("niche")
        demographic = parameters.get("demographic")
        desire = parameters.get("desire")
        n = parameters.get("n_concepts", 3)
        return generate_concepts(niche=niche, demographic=demographic, desire=desire, n_concepts=n)

    elif phase == "outline":
        concept = parameters.get("concept", {})
        return create_outline(concept)

    elif phase == "write_chapter":
        return write_chapter(
            book_title=parameters.get("book_title"),
            chapter_number=parameters.get("chapter_number"),
            chapter_title=parameters.get("chapter_title"),
            chapter_brief=parameters.get("chapter_brief"),
            book_context=parameters.get("book_context", "")
        )

    elif phase == "optimize":
        concept = parameters.get("concept", {})
        return optimize_book(concept)

    elif phase == "compile":
        book_title = parameters.get("book_title")
        from writing_agent import compile_manuscript
        path = compile_manuscript(book_title)
        return {"status": "complete", "path": path}

    return {"status": "unknown_phase"}


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "run_pipeline_phase":
        result = execute_phase(tool_input["phase"], tool_input.get("parameters", {}))
        return json.dumps(result)
    elif tool_name == "check_pipeline_status":
        return json.dumps(tool_input)
    elif tool_name == "ask_user":
        print(f"\n[Agent Question] {tool_input['question']}")
        if tool_input.get("options"):
            for i, opt in enumerate(tool_input["options"], 1):
                print(f"  {i}. {opt}")
        answer = input("\nYour answer: ")
        return json.dumps({"user_answer": answer})
    elif tool_name == "select_book_to_write":
        print(f"\n[Selection] Writing: {tool_input['selected_book']}")
        print(f"  Rationale: {tool_input['rationale']}")
        return json.dumps({"status": "selected", "book": tool_input["selected_book"]})
    return json.dumps({"status": "unknown_tool"})


def run_autonomous(goal: str = None, user_profile: dict = None) -> dict:
    """
    Main autonomous loop. Runs the full publishing pipeline with minimal human input.
    """
    profile_context = ""
    if user_profile:
        profile_context = f"\n\nUser Profile:\n{json.dumps(user_profile, indent=2)}"

    # Check for existing work
    existing = load_all_findings()
    existing_context = ""
    if existing:
        existing_context = f"\n\nExisting research in memory ({len(existing)} findings already saved)."

    query = goal or f"""Run the full KDP publishing pipeline autonomously.

    Goal: Identify the single best book opportunity right now, produce the outline,
    write the first 3 chapters, and create the full Amazon listing package.

    Steps to execute:
    1. check_pipeline_status — assess what's done and what's needed
    2. run_pipeline_phase (research) — scan key categories
    3. run_pipeline_phase (niche_discovery) — find top opportunities
    4. run_pipeline_phase (concept_generation) — build 3 book concepts
    5. select_book_to_write — pick the best one
    6. run_pipeline_phase (outline) — create full chapter outline
    7. run_pipeline_phase (write_chapter) x3 — write opening 3 chapters
    8. run_pipeline_phase (optimize) — build Amazon listing
    9. check_pipeline_status — report completion

    Ask user questions only when absolutely necessary.
    Make all decisions within your capability autonomously.{profile_context}{existing_context}"""

    messages = [{"role": "user", "content": query}]
    output = []

    while True:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=ORCHESTRATOR_TOOLS,
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

    return {"status": "complete", "output": output}


def quick_book(concept_name: str) -> dict:
    """
    Fast track: skip research/niche phases, go straight to outline + write for a known concept.
    Use when you already know what book you want to write.
    """
    # Load any existing concepts matching the name
    concepts = []
    for fname in os.listdir(BOOK_IDEAS_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(BOOK_IDEAS_DIR, fname)) as f:
                data = json.load(f)
                if concept_name.lower() in data.get("data", {}).get("working_title", "").lower():
                    concepts.append(data["data"])

    if concepts:
        concept = concepts[0]
    else:
        # Generate concept on the fly
        result = generate_concepts(niche=concept_name, n_concepts=1)
        concept = {"working_title": concept_name, "genre": "Non-fiction"}

    print(f"Fast-tracking: {concept.get('working_title')}")

    outline = create_outline(concept)
    optimize_book(concept)

    return {"status": "complete", "concept": concept}


if __name__ == "__main__":
    print("=" * 50)
    print("   KDP PUBLISHING AUTOMATION AGENT")
    print("=" * 50)
    print("\nOptions:")
    print("  1. Full autonomous pipeline (research → publish)")
    print("  2. Fast-track a specific book")
    print("  3. Research only")

    choice = input("\nChoice (1/2/3): ").strip()

    if choice == "1":
        print("\nStarting full autonomous pipeline...")
        result = run_autonomous()
        for line in result["output"]:
            print(line)

    elif choice == "2":
        book_name = input("Book title/concept: ").strip()
        quick_book(book_name)

    elif choice == "3":
        topic = input("Research topic (or press Enter for full scan): ").strip() or None
        result = run_research(topic=topic)
        for f in result["findings"]:
            print(f["content"])
