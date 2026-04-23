"""
KDP Publishing System — Shared Configuration
All agents import from here.
"""

import os
import anthropic
from dotenv import load_dotenv

# Load .env file if present
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Anthropic API key — set in .env file or environment variable
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

if not ANTHROPIC_API_KEY:
    raise EnvironmentError(
        "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
    )

# Anthropic client factory — all agents call get_client()
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Models
DEFAULT_MODEL = "claude-opus-4-7"   # Best quality — used for all core agents
FAST_MODEL    = "claude-sonnet-4-6" # Faster/cheaper — used for quick tasks

# File paths
BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_DIR   = os.path.join(BASE_DIR, "research")
BOOK_IDEAS_DIR = os.path.join(BASE_DIR, "book-ideas")
MANUSCRIPTS_DIR= os.path.join(BASE_DIR, "manuscripts")
MARKETING_DIR  = os.path.join(BASE_DIR, "marketing")
AGENTS_DIR     = os.path.join(BASE_DIR, "agents")
MEMORY_DIR     = os.path.join(BASE_DIR, "agents", "memory")

# Ensure all output directories exist
for _dir in [RESEARCH_DIR, BOOK_IDEAS_DIR, MANUSCRIPTS_DIR, MARKETING_DIR, MEMORY_DIR]:
    os.makedirs(_dir, exist_ok=True)

# KDP Constants
KDP_MAX_KEYWORDS              = 7
KDP_CATEGORIES_PER_BOOK       = 2
KDP_SWEET_SPOT_PRICE_MIN      = 2.99
KDP_SWEET_SPOT_PRICE_MAX      = 9.99
KDP_ROYALTY_70_PCT_THRESHOLD  = 2.99

# Recommended KDP categories to scan
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

# Human psychological desire clusters (drives the Psychology & Niche agents)
DESIRE_CLUSTERS = {
    "survival": [
        "money security",
        "job stability",
        "financial safety",
        "debt freedom",
        "recession prep",
    ],
    "status": [
        "respect",
        "attractiveness",
        "social proof",
        "success signals",
        "admiration",
        "career advancement",
    ],
    "love": [
        "romantic love",
        "belonging",
        "deep connection",
        "being chosen",
        "partnership",
        "healing loneliness",
    ],
    "identity": [
        "purpose",
        "self-image",
        "values alignment",
        "authenticity",
        "legacy",
        "neurodivergent identity",
        "late diagnosis",
    ],
    "health": [
        "energy",
        "longevity",
        "appearance",
        "mental clarity",
        "pain relief",
        "perimenopause",
        "hormonal health",
    ],
    "growth": [
        "learning",
        "mastery",
        "skill building",
        "transformation",
        "becoming",
        "second chapter",
    ],
    "freedom": [
        "time freedom",
        "location freedom",
        "financial freedom",
        "creative freedom",
        "early retirement",
        "digital nomad",
    ],
}
