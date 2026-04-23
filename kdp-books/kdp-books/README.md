# Book OS — AI-Powered Nonfiction Publishing System

A full-stack agentic system for writing, evaluating, and publishing nonfiction books.
Not a chatbot. A supervised production pipeline with strict gates, structured memory, and rubric-based quality control.

---

## What This Is

Most book-writing AI systems fail because they:
- Write before planning
- Keep memory only in chat context (so chapters repeat each other)
- Lack critique loops (so bad output moves forward unchecked)
- Let the "writer" define quality (no external standard)

This system fixes all of that by locking strategy first, externalising memory into files, using structured outputs with schema validation, forcing critique before progress, and updating chapter ledgers after every approval.

---

## System Architecture

### V3 Core Pipeline (11 Agents)

| Agent | File | Job |
|---|---|---|
| Input Normalizer | `input_normalizer.py` | Converts raw user request to clean publishing input |
| Book Strategist | `book_strategist.py` | Creates master brief + voice bible (most important artifact) |
| Premise Stress Tester | `premise_stress_tester.py` | Attacks the brief before any writing starts |
| Market Researcher | `research_agent.py` | Maps reader desires, objections, and positioning gaps |
| Outline Architect | `outline_architect.py` | Builds chapter progression — every chapter one new idea |
| Chapter Planner | `chapter_planner.py` | Converts outline entry into strict chapter packet (contract) |
| Chapter Drafter | `chapter_drafter.py` | Writes prose from packet — no improvisation |
| Developmental Critic | `developmental_critic.py` | Main quality gate — scores all chapters against hard thresholds |
| Chapter Rewriter | `chapter_drafter.py` | Fixes only flagged issues — max 3 revisions before human escalation |
| Line Editor | `line_editor.py` | Prose polish without structural changes |
| Continuity Editor | `continuity_editor.py` | Full-manuscript audit before assembly |

### V2 Evaluation Layer (7 Agents)

| Agent | File | Job |
|---|---|---|
| Rubric Judge | `rubric_judge.py` | Scores every artifact against structured rubric criteria |
| Claim Extractor | `claim_extractor.py` | Converts chapter prose into machine-checkable claim list |
| Grounding Auditor | `grounding_auditor.py` | Verifies claims are supported — not just plausible |
| Uncertainty Router | `uncertainty_router.py` | Routes to auto-approve, rewrite, or human based on scores |
| Pairwise Comparator | `pairwise_comparator.py` | Compares versions — keeps better, rejects worse |
| Failure Miner | `failure_miner.py` | Turns repeated mistakes into permanent prevention rules |
| Commercial Evaluator | `commercial_evaluator.py` | Checks manuscript is positioned to actually sell |

---

## Pipeline Order

```
1.  Normalize input
2.  Create book brief                ← HUMAN GATE
3.  Build voice bible + banned patterns
4.  Stress-test premise
5.  Research market
6.  Build outline
7.  Critique outline                 ← auto gate (duplicate ideas = reject)
8.  Approve outline                  ← HUMAN GATE
9.  [For each chapter, sequentially]:
    a. Build chapter packet          ← auto gate (empty = reject)
    b. Draft chapter
    c. Critique chapter              ← auto gate (loop up to 3x)
    d. Rewrite if needed
    e. Compare versions if rewrite
    f. Extract claims + audit grounding
    g. Route uncertainty
    h. Line edit
    i. Update memory
    j. Human approval (chapter 1 ONLY — mandatory)
10. Mine failure patterns
11. Continuity pass                  ← flags go back to rewrite loop
12. Assemble manuscript              ← blocked until continuity is clean
13. Evaluate commercial readiness
14. Export final assets
```

---

## Quality Thresholds

| Signal | Threshold | Action |
|---|---|---|
| Chapter rubric score | ≥ 8.0 | Auto-approve |
| Chapter rubric score | 6.5 – 7.9 | Auto-rewrite |
| Chapter rubric score | < 6.5 | Human review |
| Novelty score | < 7.0 | Rewrite |
| Clarity score | < 7.0 | Rewrite |
| Reader value score | < 7.0 | Rewrite |
| Redundancy risk | > 4.0 | Rewrite |
| Groundedness | ≥ 0.85 | Auto-approve |
| Groundedness | 0.70 – 0.84 | Rewrite flagged claims |
| Groundedness | < 0.70 | Block + escalate |
| Critic confidence | < 0.65 | Human review |
| Revision count | ≥ 3 | Human review |
| Evidence risk | > 6.0 | Human review |
| Same failure | 3× | Add to banned_patterns.json |
| Same failure | 5× | Regression test required |

---

## Memory Files

All persistent memory lives in `memory/`. No agent trusts in-context memory alone.

```
memory/
  normalized_input.json        — clean project definition
  book_brief.json              — master brief (approved by human)
  premise_report.json          — stress test results
  market_map.json              — reader + market research
  outline_locked.json          — approved outline (immutable)
  voice_bible.json             — writing style contract
  banned_patterns.json         — structural anti-patterns
  chapter_ledger.json          — what each chapter established
  concept_ledger.json          — all defined terms
  prior_chapter_summaries.json — chapter summaries for redundancy checking
  evidence_register.json       — sensitive claims register
  failure_patterns.json        — recurring failure modes (auto-updated)
  quality_dashboard.json       — aggregate quality metrics
  human_review_queue.json      — items awaiting human judgment
  run_state.json               — pipeline state for resumption

  rubrics/
    brief_rubric.json
    outline_rubric.json
    chapter_rubric.json
    continuity_rubric.json
    grounding_rubric.json
    commercial_rubric.json

  claims/
    claims_chapter_01.json     — extracted claims per chapter
    ...

  grounding/
    grounding_report_chapter_01.json
    ...

  version_comparisons/
    compare_chapter_01_v1_vs_v2.json
    ...
```

---

## Quick Start

### 1. Install dependencies

```bash
cd kdp-books/agents
pip install -r requirements.txt
```

### 2. Set your API key

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 3. Define your book

Edit `input/project_request.json` with your book details.
A template is already filled in for *The Man She Stays For*.

### 4. Run the pipeline

```bash
# Full pipeline with human approval gates
python langgraph_orchestrator.py

# Auto-approve mode (testing only — skips human gates)
python langgraph_orchestrator.py --auto

# Resume from last save point
python langgraph_orchestrator.py --resume

# Use a different project file
python langgraph_orchestrator.py --project input/my_other_book.json
```

### 5. Run individual agents (for testing)

```bash
# Test just the premise stress tester
python premise_stress_tester.py

# Test just the rubric judge
python rubric_judge.py

# Test just the chapter critic
python developmental_critic.py
```

---

## Output Files

After the pipeline completes:

```
output/
  manuscript_v1.md         — full assembled manuscript
  continuity_report.json   — cross-chapter issues
  commercial_readiness.json — market positioning assessment
  editorial_report.json    — pipeline summary (chapters, words, scores)

chapters/
  chapter_packet_01.json   — planning contract for each chapter
  chapter_draft_01.md      — raw draft
  chapter_dev_report_01.json — critic scores
  chapter_rewrite_01_v1.md — first rewrite (if needed)
  chapter_polished_01.md   — final approved chapter
```

---

## Human Gates

Three points require human approval before the pipeline continues:

1. **Book brief** — After the strategist creates it. If this is weak, everything downstream is weak.
2. **Outline** — After critique passes. Ask: "Would I buy this structure?"
3. **Chapter 1** — Mandatory. If chapter 1 misses the mark, don't automate chapters 2–10.

All other quality decisions are handled automatically by the rubric judge and uncertainty router.

---

## Running on a Phone (Termux / Replit)

On Android: Install **Termux**, then:
```bash
pkg install python
pip install anthropic python-dotenv langgraph
```

Easiest option: use **Replit** (replit.com) — paste the project, add your `.env`, run from browser.

---

## Cost Estimate

A full 10-chapter book pipeline with critique loops runs approximately:
- ~$3–8 in Anthropic credits using `claude-opus-4-7`
- ~$1–3 using `claude-sonnet-4-6` (change `DEFAULT_MODEL` in `config.py`)

The evaluation layer (rubric judge, claim extractor, grounding auditor) adds ~15–20% to total cost.

---

## Project: The Man She Stays For

This system is pre-configured with the book brief for:

**Title:** *The Man She Stays For: What Women Actually Respond To — And Why Most Men Never Figure It Out*

- **Target reader:** Men 22–45, intelligent, self-aware, keep getting the same results
- **Voice:** Direct, peer-level, no coaching-speak, British/neutral English
- **10 chapters + intro + conclusion (~40,000 words)**

Chapter 1 (*Presence Over Performance*) is already written and saved in `manuscripts/`.
Run the pipeline from chapter 2 onwards by setting `"current_chapter": 2` in `memory/run_state.json`.
