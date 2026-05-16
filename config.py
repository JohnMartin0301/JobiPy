"""
config.py — Centralized configuration for Job Alert Bot.
Load all secrets from .env; provide typed constants for the rest.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Discord
# ─────────────────────────────────────────────
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

# ─────────────────────────────────────────────
# Gmail SMTP
# ─────────────────────────────────────────────
GMAIL_SENDER: str    = os.getenv("GMAIL_SENDER", "")
GMAIL_PASSWORD: str  = os.getenv("GMAIL_PASSWORD", "")   # App password recommended
GMAIL_RECIPIENT: str = os.getenv("GMAIL_RECIPIENT", "")

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/jobs.db")

# ─────────────────────────────────────────────
# Scheduling
# ─────────────────────────────────────────────
SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "20"))

# ─────────────────────────────────────────────
# Notification thresholds
# ─────────────────────────────────────────────
DISCORD_MAX_JOBS: int = 5          # Jobs 1-5 → full Discord cards
FRESHNESS_DISCORD_MAX_DAYS: int = 7   # 0-7 days → Discord
FRESHNESS_GMAIL_MAX_DAYS: int = 14    # 8-14 days → Gmail digest
FRESHNESS_REJECT_DAYS: int = 14       # > 14 days → reject

# ─────────────────────────────────────────────
# Freshness scoring bonuses (additive)
# ─────────────────────────────────────────────
FRESHNESS_BONUS = {
    "high":   15,   # 0-2 days
    "normal": 10,   # 3-7 days
    "low":    5,    # 8-14 days
}

# ─────────────────────────────────────────────
# High-reliability sources (missing date allowed)
# ─────────────────────────────────────────────
HIGH_RELIABILITY_SOURCES = {"google_jobs", "indeed", "onlinejobs_ph", "remoteok"}

# ─────────────────────────────────────────────
# Keyword lists
# ─────────────────────────────────────────────
INCLUDE_KEYWORDS = [
    "python", "flask", "fastapi", "api", "backend",
    "automation", "software developer", "software engineer",
    "web developer", "full stack", "fullstack", "django",
    "developer", "engineer",
]

LEVEL_KEYWORDS = [
    "junior", "entry level", "entry-level", "associate",
    "fresh graduate", "no experience required", "intern",
    "graduate", "trainee", "junior level", "0-2 years",
    "0 to 2 years", "less than 1 year", "new grad",
    "no experience", "open to fresh", "fresh grad",
    "newly grad", "recent grad", "beginner", "starter",
    "apprentice", "part time", "part-time", "freelance",
]

LOCATION_KEYWORDS = [
    "remote", "wfh", "work from home", "work-from-home",
    "hybrid", "anywhere", "worldwide", "global",
    "online", "virtual", "telecommute", "philippines",
    "work anywhere", "home based", "home-based",
    "distributed", "flexible",
]

EXCLUDE_KEYWORDS = [
    "senior", " sr ", "sr.", "lead", "principal",
    "manager", "director", "architect",
]

# ─────────────────────────────────────────────
# Source bypass rules
# Remote-only sources skip the location filter
# because every job on them is remote by definition
# ─────────────────────────────────────────────
REMOTE_ONLY_SOURCES = {"onlinejobs_ph", "remoterocketship", "remoteok"}

# Sources where junior/entry-level is implied by the platform
# (e.g. OnlineJobs.ph targets Filipino freelancers/remote workers)
JUNIOR_IMPLIED_SOURCES = {"onlinejobs_ph"}

# ─────────────────────────────────────────────
# Scoring weights
# ─────────────────────────────────────────────
SCORE_WEIGHTS = {
    "python":        30,
    "flask_fastapi": 20,
    "remote":        20,
    "junior":        20,
    "fresh_post":    15,   # posted within 0-48 hours
    "good_source":   10,   # LinkedIn / Indeed / JobStreet
}

GOOD_SOURCES_FOR_SCORE = {"linkedin", "indeed", "jobstreet", "onlinejobs_ph", "remoteok"}

# ─────────────────────────────────────────────
# URL validation
# ─────────────────────────────────────────────
URL_TIMEOUT_SECONDS: int = 10

# ─────────────────────────────────────────────
# Playwright headless flag
# ─────────────────────────────────────────────
PLAYWRIGHT_HEADLESS: bool = True