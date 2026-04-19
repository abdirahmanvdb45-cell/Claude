"""
KDP Publishing System — Shared Configuration
All agents import from here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API key — set in environment or .env file
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Model to use across all agents
DEFAULT_MODEL = "claude-opus-4-7"
FAST_MODEL = "claude-sonnet-4-6"

# File paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_DIR = os.path.join(BASE_DIR, "research")
BOOK_IDEAS_DIR = os.path.join(BASE_DIR, "book-ideas")
MANUSCRIPTS_DIR = os.path.join(BASE_DIR, "manuscripts")
MARKETING_DIR = os.path.join(BASE_DIR, "marketing")
PUBLISH_DIR = os.path.join(BASE_DIR, "publish")
AGENTS_DIR = os.path.join(BASE_DIR, "agents")
MEMORY_DIR = os.path.join(BASE_DIR, "agents", "memory")

# Ensure directories exist
for d in [RESEARCH_DIR, BOOK_IDEAS_DIR, MANUSCRIPTS_DIR, MARKETING_DIR, PUBLISH_DIR, MEMORY_DIR]:
    os.makedirs(d, exist_ok=True)

# KDP Constants
KDP_MAX_KEYWORDS = 7
KDP_CATEGORIES_PER_BOOK = 2
KDP_SWEET_SPOT_PRICE_MIN = 2.99
KDP_SWEET_SPOT_PRICE_MAX = 9.99
KDP_ROYALTY_70_PCT_THRESHOLD = 2.99

# Target book categories
TARGET_CATEGORIES = [
    "Self-Help",
    "Business & Money",
    "Health, Fitness & Dieting",
    "Relationships & Dating",
    "Mindset & Psychology",
    "Personal Finance",
    "Romance Fiction",
    "Thriller & Suspense",
    "Fantasy",
    "True Crime",
    "Parenting & Family",
    "Education & Reference",
]

# Human psychological desire clusters (used by Psychology Agent)
DESIRE_CLUSTERS = {
    "survival": ["money", "security", "job stability", "financial safety", "debt freedom"],
    "status": ["respect", "attractiveness", "social proof", "success signals", "admiration"],
    "love": ["romantic love", "belonging", "deep connection", "being chosen", "partnership"],
    "identity": ["purpose", "self-image", "values alignment", "authenticity", "legacy"],
    "health": ["energy", "longevity", "appearance", "mental clarity", "pain relief"],
    "growth": ["learning", "mastery", "skill building", "transformation", "becoming"],
    "freedom": ["time freedom", "location freedom", "financial freedom", "creative freedom"],
}
