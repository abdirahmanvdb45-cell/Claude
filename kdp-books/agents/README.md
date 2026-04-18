# KDP Publishing AI Agent System

A fully autonomous AI-powered book publishing pipeline for Amazon KDP.

## Agents Overview

| Agent | File | Role |
|---|---|---|
| Research Agent | `research_agent.py` | Scans Amazon KDP, tracks trends, stores market intelligence |
| Niche Agent | `niche_agent.py` | Finds underserved niches, maps human desires to opportunities |
| Psychology Agent | `psychology_agent.py` | Builds psychologically-engineered book concepts |
| Writing Agent | `writing_agent.py` | Writes full manuscripts chapter by chapter |
| Optimization Agent | `optimization_agent.py` | Creates KDP listings (title, keywords, description, categories) |
| Automation Agent | `automation_agent.py` | Orchestrates all agents; runs the full pipeline autonomously |

## Setup

```bash
cd kdp-books/agents
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

## Usage

### Full Autonomous Pipeline (recommended)
```bash
python automation_agent.py
# Choose option 1
```

### Fast-Track a Specific Book
```bash
python automation_agent.py
# Choose option 2, enter book name
```

### Run Individual Agents
```bash
python research_agent.py      # Market scan
python niche_agent.py         # Niche discovery
python psychology_agent.py    # Concept generation
python writing_agent.py       # Write a chapter
python optimization_agent.py  # Create Amazon listing
```

## Pipeline Flow

```
research_agent → niche_agent → psychology_agent → writing_agent → optimization_agent
     ↓                ↓               ↓                ↓                ↓
  Market data    Top niches     Book concepts      Manuscript      KDP listing
  saved to       saved to       saved to           saved to        saved to
  agents/memory  agents/memory  book-ideas/        manuscripts/    marketing/
```

## Memory System
All agents share a common memory store at `agents/memory/`.
Each agent reads findings from previous agents to build on their work.

## Output Files
- `research/` — market intelligence reports
- `book-ideas/` — psychologically-engineered book concepts (JSON)
- `manuscripts/` — chapter files + compiled manuscript (Markdown)
- `marketing/` — Amazon listing package (title options, keywords, description, categories)
