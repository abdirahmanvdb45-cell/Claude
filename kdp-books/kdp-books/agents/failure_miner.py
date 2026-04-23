"""
Failure Pattern Miner Agent — V2
Reads rejection reports and human reviewer comments, extracts recurring failure patterns,
and updates the system's memory so the same mistakes stop repeating.
"""

import json
from pathlib import Path
from datetime import datetime
from config import get_client, DEFAULT_MODEL

client = get_client()

FAILURE_PATTERNS_PATH = Path(__file__).parent / "memory" / "failure_patterns.json"
BANNED_PATTERNS_PATH = Path(__file__).parent / "memory" / "banned_patterns.json"
QUALITY_DASHBOARD_PATH = Path(__file__).parent / "memory" / "quality_dashboard.json"

REPEAT_TO_BAN_THRESHOLD = 3       # Add to failure patterns + prevention rule
REPEAT_TO_REGRESS_THRESHOLD = 5   # Flag agent prompt as degraded


def mine_failures(
    rejection_reports: list[dict],
    human_comments: list[str] | None = None,
) -> dict:
    """
    Analyse rejection reports and comments to identify recurring failure patterns.

    Args:
        rejection_reports: List of rubric judge reports with decision "rewrite", "human_review", or "rebuild"
        human_comments: Optional list of free-text comments from human reviewers.

    Returns:
        dict with new_patterns, updated_bans, summary
    """
    reports_text = json.dumps(rejection_reports, indent=2)
    comments_text = "\n".join(f"- {c}" for c in (human_comments or []))

    system_prompt = """You are the Failure Pattern Miner. You read rejection reports and human
reviewer comments to find recurring failure modes. Your job is to name the patterns precisely,
count them, assess severity, and write clear prevention rules that can be inserted into prompts
or routing logic. Output valid JSON only."""

    user_prompt = f"""Analyse these rejection reports and human comments for recurring failure patterns.

REJECTION REPORTS:
{reports_text}

HUMAN REVIEWER COMMENTS:
{comments_text or "None provided."}

Look for:
- Patterns that appear 2+ times across reports
- Structural weaknesses (bad openings, weak conclusions, unclear thesis)
- Evidence problems (unsupported claims, overextensions)
- Tone issues (drifting voice, coaching-speak, hedging)
- Redundancy problems (chapters repeating prior material)
- Commercial weaknesses (weak titles, unclear promise, thin reader value)

For each pattern found, write:
{{
  "pattern_id": "FP_XXX",
  "name": "<short label>",
  "count": <int>,
  "severity": "<low|medium|high>",
  "trigger_rule": "<what activates this pattern>",
  "prevention_rule": "<what change prevents it>",
  "prompt_addition": "<text to add to the relevant agent prompt>",
  "first_seen": "<ISO date>",
  "last_seen": "<ISO date>"
}}

Return:
{{
  "new_patterns_found": <int>,
  "patterns": [<pattern objects>],
  "summary": "<one paragraph>",
  "recommended_prompt_updates": ["<agent name>: <change>", ...]
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

    # Merge into persistent failure_patterns.json
    _update_failure_patterns(result.get("patterns", []))

    # Update banned_patterns.json for high-severity patterns that repeat enough
    _update_banned_patterns(result.get("patterns", []))

    # Update quality dashboard
    _update_quality_dashboard(result)

    print(f"\n🧠 Failure Pattern Miner")
    print(f"   New Patterns Found  : {result.get('new_patterns_found', 0)}")
    print(f"   Summary: {result.get('summary', '')[:120]}...")
    if result.get("recommended_prompt_updates"):
        print("   Recommended Updates:")
        for update in result["recommended_prompt_updates"]:
            print(f"     • {update}")

    return result


def _update_failure_patterns(new_patterns: list[dict]):
    """Merge new patterns into the persistent failure_patterns.json file."""
    FAILURE_PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(FAILURE_PATTERNS_PATH) as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {"patterns": [], "last_updated": ""}

    existing_names = {p["name"]: i for i, p in enumerate(existing["patterns"])}

    for pattern in new_patterns:
        if pattern["name"] in existing_names:
            # Increment count
            idx = existing_names[pattern["name"]]
            existing["patterns"][idx]["count"] += pattern.get("count", 1)
            existing["patterns"][idx]["last_seen"] = datetime.utcnow().isoformat()
        else:
            pattern.setdefault("first_seen", datetime.utcnow().isoformat())
            existing["patterns"].append(pattern)

    existing["last_updated"] = datetime.utcnow().isoformat()

    with open(FAILURE_PATTERNS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


def _update_banned_patterns(patterns: list[dict]):
    """Add high-severity repeated patterns to banned_patterns.json."""
    BANNED_PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(BANNED_PATTERNS_PATH) as f:
            banned = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        banned = {"banned_phrases": [], "banned_structures": [], "last_updated": ""}

    for pattern in patterns:
        if pattern.get("count", 0) >= REPEAT_TO_BAN_THRESHOLD and pattern.get("severity") == "high":
            ban_entry = {
                "name": pattern["name"],
                "prevention_rule": pattern.get("prevention_rule", ""),
                "added": datetime.utcnow().isoformat(),
                "source_pattern_id": pattern.get("pattern_id", ""),
            }
            # Avoid duplicates
            existing_names = [b.get("name") for b in banned.get("banned_structures", [])]
            if ban_entry["name"] not in existing_names:
                banned.setdefault("banned_structures", []).append(ban_entry)
                print(f"   → Banned pattern added: {pattern['name']}")

        if pattern.get("count", 0) >= REPEAT_TO_REGRESS_THRESHOLD:
            print(f"   ⚠️  REGRESSION TEST REQUIRED — pattern '{pattern['name']}' occurred {pattern['count']} times")

    banned["last_updated"] = datetime.utcnow().isoformat()

    with open(BANNED_PATTERNS_PATH, "w", encoding="utf-8") as f:
        json.dump(banned, f, indent=2)


def _update_quality_dashboard(mining_result: dict):
    """Update the quality dashboard with the latest failure mining results."""
    QUALITY_DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(QUALITY_DASHBOARD_PATH) as f:
            dashboard = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        dashboard = {
            "projects_completed": 0,
            "total_rejection_cycles": 0,
            "failure_patterns_logged": 0,
            "avg_chapter_score": 0.0,
            "avg_groundedness_score": 0.0,
            "human_review_rate": 0.0,
            "avg_revisions_per_chapter": 0.0,
            "most_common_failure_patterns": [],
            "last_updated": "",
        }

    dashboard["failure_patterns_logged"] += mining_result.get("new_patterns_found", 0)
    dashboard["last_updated"] = datetime.utcnow().isoformat()

    # Update most common patterns
    try:
        with open(FAILURE_PATTERNS_PATH) as f:
            all_patterns = json.load(f).get("patterns", [])
        sorted_patterns = sorted(all_patterns, key=lambda p: p.get("count", 0), reverse=True)
        dashboard["most_common_failure_patterns"] = [p["name"] for p in sorted_patterns[:5]]
    except Exception:
        pass

    with open(QUALITY_DASHBOARD_PATH, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2)


if __name__ == "__main__":
    sample_reports = [
        {
            "artifact_type": "chapter",
            "artifact_id": "chapter_03",
            "decision": "rewrite",
            "must_fix": ["Opening restates thesis from chapter 1", "Tone drifts into coaching-speak"],
            "weighted_score": 6.8,
        },
        {
            "artifact_type": "chapter",
            "artifact_id": "chapter_05",
            "decision": "rewrite",
            "must_fix": ["Opening restates thesis from prior chapter", "Weak practical takeaway"],
            "weighted_score": 7.1,
        },
    ]
    result = mine_failures(sample_reports, human_comments=["Too much hedging in chapter 3", "Chapter 5 felt generic"])
    print(json.dumps(result, indent=2))
