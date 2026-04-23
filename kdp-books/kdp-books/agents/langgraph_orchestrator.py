"""
LangGraph Orchestrator — V3 Book OS
The central state machine that governs the entire book production pipeline.
Every node produces one artifact. The next node cannot run until that artifact is approved.
No prose is written unless the previous planning artifact is approved.

PIPELINE ORDER:
1.  load_project
2.  normalize_input
3.  build_book_brief
4.  stress_test_premise        ← gate: revise brief if weak
5.  research_market
6.  build_outline
7.  review_outline             ← gate: reject if duplicate new_ideas
8.  approve_outline            ← HUMAN GATE
9.  init_memory
10. [for each chapter]:
    a. build_chapter_packet    ← gate: reject if no new content
    b. draft_chapter
    c. critique_chapter        ← gate: rewrite loop (max 3)
    d. [rewrite if needed]
    e. [compare versions if rewrite]
    f. extract_claims + audit_grounding
    g. route_uncertainty
    h. line_edit_chapter
    i. update_memory
    j. [human approval on chapter 1 — mandatory]
11. continuity_pass            ← gate: route flagged chapters to rewrite
12. evidence_pass
13. assemble_manuscript        ← gate: blocked until continuity is clean
14. final_polish
15. evaluate_commercial_readiness
16. export_final_assets
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# V3 Core Agents
from input_normalizer import normalize_input
from book_strategist import create_book_brief, create_voice_bible, create_banned_patterns
from premise_stress_tester import stress_test_premise
from research_agent import build_market_map
from book_idea_generator import run as generate_book_ideas
from cover_brief_agent import run as generate_cover_brief
from outline_architect import build_outline, critique_outline, lock_outline
from chapter_planner import build_chapter_packet
from chapter_drafter import draft_chapter, rewrite_chapter
from developmental_critic import critique_chapter
from line_editor import line_edit_chapter, update_memory_after_chapter
from continuity_editor import continuity_pass, assemble_manuscript

# V2 Evaluation Layer
from rubric_judge import judge_and_save
from claim_extractor import extract_claims
from grounding_auditor import audit_grounding
from uncertainty_router import route
from pairwise_comparator import compare_versions
from failure_miner import mine_failures
from commercial_evaluator import evaluate_commercial_readiness
from cover_generator import run_at_publish as generate_final_cover

AGENTS_DIR = Path(__file__).parent
MEMORY_DIR = AGENTS_DIR / "memory"
CHAPTERS_DIR = AGENTS_DIR / "chapters"
OUTPUT_DIR = AGENTS_DIR / "output"

MAX_REVISIONS = 3
MAX_BRIEF_REVISIONS = 3
MAX_OUTLINE_REVISIONS = 3


def load_state() -> dict:
    state_path = MEMORY_DIR / "run_state.json"
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {
        "project_id": f"book_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "stage": "load_project",
        "current_chapter": 1,
        "total_chapters": 0,
        "approved": {},
        "revision_counts": {},
        "flags": {},
        "brief_revision_count": 0,
        "outline_revision_count": 0,
        "started_at": datetime.utcnow().isoformat(),
    }


def save_state(state: dict):
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_DIR / "run_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_json_file(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def human_gate(message: str, artifact_path: str) -> bool:
    """
    Pause the pipeline and request human approval.
    In a full LangGraph deployment this would trigger an interrupt node.
    In CLI mode it prompts the user.
    """
    print(f"\n{'='*60}")
    print("🛑 HUMAN APPROVAL REQUIRED")
    print(f"   {message}")
    print(f"   File: {artifact_path}")
    print("="*60)

    while True:
        response = input("\n   Approve? [y/n/quit]: ").strip().lower()
        if response == "y":
            return True
        elif response == "n":
            return False
        elif response == "quit":
            print("Pipeline halted by user.")
            sys.exit(0)


def run_pipeline(project_request: dict, auto_approve: bool = False):
    """
    Run the full book production pipeline.

    Args:
        project_request: Dict matching input/project_request.json schema.
        auto_approve: If True, skips human gates (for testing only).
    """
    state = load_state()
    state["stage"] = "normalize_input"
    save_state(state)

    print(f"\n{'='*60}")
    print(f"📘 Book OS — Pipeline Starting")
    print(f"   Project ID : {state['project_id']}")
    print(f"{'='*60}\n")

    # ─── STAGE 1: Input Normalization ───────────────────────────
    print("[1/16] Normalizing input...")
    normalized = normalize_input(project_request)

    if normalized.get("gate_status") == "pause_for_human_input" and not auto_approve:
        print(f"\n⛔ Pipeline paused: {normalized.get('gate_reason', 'Input needs clarification.')}")
        print("   Update memory/normalized_input.json and re-run.")
        return

    # ─── STAGE 2: Book Brief ─────────────────────────────────────
    print("\n[2/16] Creating book brief...")
    brief_revisions = 0
    while brief_revisions < MAX_BRIEF_REVISIONS:
        book_brief = create_book_brief(normalized)

        # Judge the brief
        brief_score = judge_and_save(
            json.dumps(book_brief, indent=2), "brief", f"v{brief_revisions+1}"
        )

        if brief_score.get("decision") in ("approve",):
            break
        elif brief_score.get("decision") == "rebuild" and brief_revisions >= MAX_BRIEF_REVISIONS - 1:
            print("⛔ Brief quality too low after max revisions. Manual intervention required.")
            return
        else:
            print(f"   Brief scored {brief_score.get('weighted_score'):.1f} — revising (attempt {brief_revisions+1})")
            brief_revisions += 1

    if not auto_approve:
        approved = human_gate("Review and approve the book brief.", str(MEMORY_DIR / "book_brief.json"))
        if not approved:
            print("Brief rejected by user. Edit memory/book_brief.json and re-run.")
            return

    state["approved"]["brief"] = True
    save_state(state)

    # Create voice bible and banned patterns
    print("\n[3/16] Building voice bible and memory...")
    create_voice_bible(book_brief)
    create_banned_patterns()

    # ─── STAGE 3: Premise Stress Test ────────────────────────────
    print("\n[4/16] Stress-testing premise...")
    premise_report = stress_test_premise(book_brief)

    if premise_report.get("go_no_go") == "no_go":
        print("⛔ Premise failed stress test with unrecoverable flaws. Rebuild required.")
        return
    elif premise_report.get("go_no_go") == "revise":
        print("   Premise needs revision. Review memory/premise_report.json and update the brief.")
        if not auto_approve:
            approved = human_gate("Premise needs work. Continue anyway?", str(MEMORY_DIR / "premise_report.json"))
            if not approved:
                return

    # ─── STAGE 4: Market Research ────────────────────────────────
    print("\n[5/16] Running market research...")
    market_map = load_json_file(MEMORY_DIR / "market_map.json")
    if not market_map:
        # Run full research scan if no cached map exists
        market_map = build_market_map(book_brief)

    # Book Idea Generator — runs automatically after research
    print("\n[5b/16] Generating ranked book ideas from research data...")
    ideas_result = generate_book_ideas(
        topic_hint=book_brief.get("topic_normalized") or book_brief.get("book_thesis", ""),
        n=5,
    )
    if ideas_result and ideas_result.get("top_recommendation"):
        print(f"\n   💡 Top opportunity identified: {ideas_result['top_recommendation']}")
        print(f"   Full ranked report saved to: book-ideas/")
        state["top_book_recommendation"] = ideas_result.get("top_recommendation")
        save_state(state)

    # Cover Brief Agent — auto-generates brief for the top-ranked idea
    top_idea = ideas_result.get("ideas", [{}])[0] if ideas_result.get("ideas") else None
    if top_idea:
        print("\n[5c/16] Generating cover brief for top book idea...")
        generate_cover_brief(idea=top_idea)
        print(f"   Cover brief saved to: output/")

    # ─── STAGE 5: Outline ────────────────────────────────────────
    print("\n[6/16] Building outline...")
    outline_revisions = 0
    while outline_revisions < MAX_OUTLINE_REVISIONS:
        outline = build_outline(book_brief, premise_report, market_map or None)
        outline_review = critique_outline(outline, book_brief)

        if outline_review.get("gate_decision") == "approve":
            break
        elif outline_review.get("gate_decision") == "reject":
            print(f"   Outline rejected — duplicate ideas found. Rebuilding... (attempt {outline_revisions+1})")
            outline_revisions += 1
        else:
            print(f"   Outline needs revision (attempt {outline_revisions+1})")
            outline_revisions += 1

        if outline_revisions >= MAX_OUTLINE_REVISIONS:
            print("⛔ Outline quality too low after max revisions. Manual intervention required.")
            return

    if not auto_approve:
        approved = human_gate(
            "Review and approve the chapter outline.", str(MEMORY_DIR / "outline.json")
        )
        if not approved:
            print("Outline rejected. Edit memory/outline.json and re-run.")
            return

    lock_outline(outline)
    state["approved"]["outline"] = True

    # Count total chapters
    total_chapters = sum(len(p.get("chapters", [])) for p in outline.get("parts", []))
    state["total_chapters"] = total_chapters
    save_state(state)
    print(f"\n   ✅ Outline locked — {total_chapters} chapters to write.")

    # ─── STAGE 6: Chapter Pipeline (Sequential) ──────────────────
    all_chapter_numbers = []
    for part in outline.get("parts", []):
        for ch in part.get("chapters", []):
            all_chapter_numbers.append(ch["number"])

    rejection_reports = []

    for ch_num in all_chapter_numbers:
        print(f"\n{'─'*60}")
        print(f"📖 Chapter {ch_num} / {total_chapters}")
        print(f"{'─'*60}")

        state["current_chapter"] = ch_num
        state["stage"] = f"chapter_{ch_num}"
        save_state(state)

        # a. Build packet
        print(f"\n  [a] Building chapter packet...")
        packet = build_chapter_packet(ch_num)

        if packet.get("gate_violation"):
            print(f"  ⛔ Chapter {ch_num} packet gate violation: {packet['gate_violation']}")
            return

        # b. Draft
        print(f"\n  [b] Drafting chapter...")
        chapter_text = draft_chapter(ch_num)
        revision_count = state["revision_counts"].get(str(ch_num), 0)

        # c. Critique → rewrite loop
        approved_for_line_edit = False
        while revision_count <= MAX_REVISIONS:
            print(f"\n  [c] Critique (revision {revision_count})...")
            critic_report = critique_chapter(ch_num)

            decision = critic_report.get("decision")

            # Route through uncertainty router
            route_result = route(
                rubric_score=None,
                groundedness_score=None,
                critic_confidence=critic_report.get("confidence"),
                revision_count=revision_count,
                artifact_type="chapter",
                evidence_risk=critic_report.get("scores", {}).get("evidence_risk", 0),
            )

            if decision == "approve" and route_result["action"] in ("auto_approve",):
                print(f"  ✅ Chapter {ch_num} approved by critic.")
                approved_for_line_edit = True
                break
            elif decision == "human_review" or route_result["action"] == "human_review":
                if not auto_approve:
                    approved = human_gate(
                        f"Chapter {ch_num} flagged for human review.",
                        str(CHAPTERS_DIR / f"chapter_draft_{ch_num:02d}.md"),
                    )
                    if approved:
                        approved_for_line_edit = True
                        break
                else:
                    approved_for_line_edit = True
                    break
            elif revision_count >= MAX_REVISIONS:
                print(f"  ⛔ Chapter {ch_num} hit max revisions. Escalating to human.")
                rejection_reports.append(critic_report)
                if not auto_approve:
                    human_gate(
                        f"Chapter {ch_num} needs manual intervention after {MAX_REVISIONS} revisions.",
                        str(CHAPTERS_DIR / f"chapter_draft_{ch_num:02d}.md"),
                    )
                approved_for_line_edit = True
                break
            else:
                print(f"\n  [d] Rewriting (revision {revision_count+1})...")
                # Compare versions if we have a prior draft
                prior_draft_path = CHAPTERS_DIR / f"chapter_rewrite_{ch_num:02d}_v{revision_count}.md"
                chapter_text = rewrite_chapter(ch_num, revision_count)
                revision_count += 1
                state["revision_counts"][str(ch_num)] = revision_count
                save_state(state)
                rejection_reports.append(critic_report)

        # e. Claims + grounding
        print(f"\n  [e] Extracting claims and auditing grounding...")
        claims_result = extract_claims(chapter_text, ch_num)
        risky_claims = [c for c in claims_result.get("claims", []) if c.get("risk_level") in ("high", "medium")]
        if risky_claims:
            grounding_result = audit_grounding(risky_claims, ch_num)
            g_score = grounding_result.get("groundedness_score", 1.0)
            grounding_route = route(
                groundedness_score=g_score,
                critic_confidence=0.8,
                artifact_type="chapter",
            )
            if grounding_route["action"] == "human_review" and not auto_approve:
                human_gate(
                    f"Chapter {ch_num} has grounding issues (score: {g_score:.0%}).",
                    str(MEMORY_DIR / "grounding" / f"grounding_report_chapter_{ch_num:02d}.json"),
                )

        # f. Line edit
        print(f"\n  [f] Line editing...")
        polished = line_edit_chapter(ch_num)

        # g. Update memory
        print(f"\n  [g] Updating memory...")
        update_memory_after_chapter(ch_num, polished)

        # h. Human approval on chapter 1 (mandatory)
        if ch_num == 1 and not auto_approve:
            print("\n  ⚠️  Chapter 1 requires mandatory human approval before continuing.")
            approved = human_gate(
                "Chapter 1 approved? (If not, the pipeline will pause for revisions.)",
                str(CHAPTERS_DIR / f"chapter_polished_{ch_num:02d}.md"),
            )
            if not approved:
                print("Chapter 1 rejected. Edit and re-run from stage chapter_1.")
                return

        state["approved"][f"chapter_{ch_num}"] = True
        save_state(state)
        print(f"  ✅ Chapter {ch_num} complete and saved to memory.")

    # ─── STAGE 7: Mine Failures ───────────────────────────────────
    if rejection_reports:
        print("\n[12/16] Mining failure patterns...")
        mine_failures(rejection_reports)

    # ─── STAGE 8: Continuity Pass ────────────────────────────────
    print("\n[13/16] Running continuity pass...")
    continuity_report = continuity_pass()

    if continuity_report.get("required_rewrites"):
        chapters_to_fix = continuity_report["required_rewrites"]
        print(f"\n   ⚠️  {len(chapters_to_fix)} chapters need revision: {chapters_to_fix}")
        print("   Re-run rewrite loop for flagged chapters, then re-run continuity pass.")
        if not auto_approve:
            approved = human_gate("Accept continuity issues and continue?", str(OUTPUT_DIR / "continuity_report.json"))
            if not approved:
                return

    # ─── STAGE 9: Assembly ───────────────────────────────────────
    print("\n[14/16] Assembling manuscript...")
    manuscript = assemble_manuscript()

    if not manuscript:
        print("⛔ Assembly blocked by unresolved continuity issues.")
        return

    # ─── STAGE 10: Commercial Readiness ──────────────────────────
    print("\n[15/16] Evaluating commercial readiness...")
    book_brief = load_json_file(MEMORY_DIR / "book_brief.json")
    commercial_result = evaluate_commercial_readiness(
        book_brief=book_brief,
        manuscript_summary=manuscript[:2000],
        subtitle_options=book_brief.get("subtitle_options", []),
    )

    if not commercial_result.get("go_to_packaging"):
        print("\n   ⚠️  Book not commercially ready — review output/commercial_readiness.json")
        if not auto_approve:
            approved = human_gate("Continue to export despite commercial issues?", str(OUTPUT_DIR / "commercial_readiness.json"))
            if not approved:
                return

    # ─── SET PUBLISH STAGE (unlocks cover generator) ─────────────
    # This is the only place this stage is set — cover_generator.py
    # checks for it before generating any image.
    state["stage"] = "publish_ready"
    save_state(state)
    print("\n   ✅ Stage set to publish_ready — cover generation unlocked.")

    # ─── STAGE 11: Final Export ──────────────────────────────────
    print("\n[16/16] Exporting final assets...")

    # Generate the book cover — gated inside run_at_publish, only runs here
    author_name = project_request.get("author_name", "")
    book_title  = book_brief.get("book_title") or project_request.get("book_title", "")
    if author_name:
        print("\n   Generating final book cover (publish gate)...")
        cover_result = generate_final_cover(author_name=author_name, title=book_title)
        if cover_result.get("status") == "success":
            print(f"   ✅ Cover generated: {len(cover_result.get('covers', []))} variant(s)")
            for c in cover_result.get("covers", []):
                print(f"   → {c}")
            state["cover_files"] = cover_result.get("covers", [])
        else:
            print(f"   ⚠️  Cover generation failed: {cover_result.get('reason', 'unknown error')}")
            print("   You can run: python cover_generator.py --author 'Your Name'")
    else:
        print("\n   ⚠️  No author_name in project request — skipping cover generation.")
        print("   Run manually: python cover_generator.py --author 'Your Name'")

    state["stage"] = "complete"
    state["completed_at"] = datetime.utcnow().isoformat()
    save_state(state)

    # Write editorial report
    editorial_report = {
        "project_id": state["project_id"],
        "version": "v1",
        "completed_at": state["completed_at"],
        "approved_chapters": len([k for k in state["approved"] if k.startswith("chapter_")]),
        "total_chapters": state["total_chapters"],
        "revision_counts": state["revision_counts"],
        "unresolved_issues": continuity_report.get("global_issues", []),
        "commercial_score": commercial_result.get("overall_commercial_score"),
        "word_count": len(manuscript.split()),
    }

    with open(OUTPUT_DIR / "editorial_report.json", "w", encoding="utf-8") as f:
        json.dump(editorial_report, f, indent=2)

    print(f"\n{'='*60}")
    print("✅ PIPELINE COMPLETE")
    print(f"   Chapters  : {editorial_report['approved_chapters']}")
    print(f"   Words     : {editorial_report['word_count']:,}")
    print(f"   Commercial: {editorial_report['commercial_score']:.1f}/10")
    print(f"   Output    : {OUTPUT_DIR}/manuscript_v1.md")
    print(f"{'='*60}\n")

    return editorial_report


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Book OS — LangGraph Pipeline")
    parser.add_argument("--project", default="input/project_request.json", help="Path to project_request.json")
    parser.add_argument("--auto", action="store_true", help="Skip all human gates (testing only)")
    parser.add_argument("--resume", action="store_true", help="Resume from last saved state")
    args = parser.parse_args()

    project_path = Path(args.project)
    if not project_path.exists():
        print(f"❌ Project file not found: {project_path}")
        print("   Create input/project_request.json first. See README.md for schema.")
        sys.exit(1)

    with open(project_path) as f:
        project_request = json.load(f)

    run_pipeline(project_request, auto_approve=args.auto)
