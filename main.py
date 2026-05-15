"""
main.py — Job Alert Bot orchestrator.

Pipeline (in order):
  1. Scrape  → collect raw jobs from all sources
  2. Filter  → keyword / level / location gate
  3. Freshness → compute tier, reject stale posts
  4. Deduplicate → skip known jobs
  5. Validate → check URLs are reachable
  6. Score   → rank by relevance
  7. Notify  → route to Discord or Gmail

Run modes:
  python main.py            — single run
  python main.py --schedule — loop every SCRAPE_INTERVAL_MINUTES minutes
"""

import sys
import time
import logging
import argparse
from datetime import datetime

import database
from config import SCRAPE_INTERVAL_MINUTES, DISCORD_MAX_JOBS

from scrapers import google_jobs, indeed, jobstreet, linkedin, facebook, onlinejobs, remoterocketship
from filters.keyword_filter  import passes_keyword_filter
from filters.level_filter    import evaluate_freshness, freshness_bonus, notification_channel
from filters.duplicate_filter import is_new_job, reset_run_cache
from filters.scoring          import score_job
from utils.hash_generator     import generate_hash
from utils.url_validator      import is_valid_url
from notifier import discord as discord_notifier
from notifier import gmail   as gmail_notifier

# ──────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ──────────────────────────────────────────────────────────────
# Scraper registry
# ──────────────────────────────────────────────────────────────
SCRAPERS = [
    ("Google Jobs / RemoteOK", google_jobs.scrape),
    ("Indeed",                 indeed.scrape),
    ("JobStreet",              jobstreet.scrape),
    ("OnlineJobs.ph",          onlinejobs.scrape),
    ("Remote Rocketship",      remoterocketship.scrape),
    ("LinkedIn",               linkedin.scrape),
    ("Facebook",               facebook.scrape),
]


def collect_raw_jobs() -> list[dict]:
    """Run all scrapers and merge results."""
    all_jobs: list[dict] = []
    for name, scrape_fn in SCRAPERS:
        try:
            results = scrape_fn()
            logger.info("%-25s → %d jobs", name, len(results))
            all_jobs.extend(results)
        except Exception as exc:
            logger.error("Scraper '%s' crashed: %s", name, exc)
    return all_jobs


def run_pipeline() -> None:
    """Full scrape-to-notify pipeline."""
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("Job Alert Bot — cycle started at %s", start.strftime("%Y-%m-%d %H:%M:%S"))

    reset_run_cache()

    # ── 1. Scrape
    raw_jobs = collect_raw_jobs()
    logger.info("Total raw jobs collected: %d", len(raw_jobs))

    # ── 2 → 6. Filter, freshness, dedup, validate, score
    discord_queue: list[dict] = []
    gmail_queue:   list[dict] = []
    stats = {"total": len(raw_jobs), "filtered": 0, "stale": 0, "dupes": 0,
             "bad_url": 0, "discord": 0, "gmail": 0}

    for job in raw_jobs:
        # ── 2. Keyword / level / location filter
        if not passes_keyword_filter(job):
            stats["filtered"] += 1
            continue

        # ── 3. Freshness check (BEFORE dedup and scoring)
        tier = evaluate_freshness(job)
        if tier == "reject":
            stats["stale"] += 1
            continue

        channel = notification_channel(tier)
        if channel == "discard":
            stats["stale"] += 1
            continue

        # ── 4. Duplicate check
        hash_id = generate_hash(
            job.get("job_title", ""),
            job.get("company", ""),
            job.get("job_url", ""),
        )
        if not is_new_job(hash_id):
            stats["dupes"] += 1
            continue

        # ── 5. URL validation
        if not is_valid_url(job.get("job_url", "")):
            logger.debug("Bad URL skipped: %s", job.get("job_url"))
            stats["bad_url"] += 1
            continue

        # ── 6. Score
        bonus = freshness_bonus(tier)
        job["score"]         = score_job(job, freshness_bonus=bonus)
        job["freshness_tier"] = tier
        job["hash_id"]        = hash_id

        # ── Route
        if channel == "discord":
            discord_queue.append(job)
            stats["discord"] += 1
        else:
            gmail_queue.append(job)
            stats["gmail"] += 1

    # Sort both queues by score descending
    discord_queue.sort(key=lambda j: j["score"], reverse=True)
    gmail_queue.sort(key=lambda j: j["score"], reverse=True)

    logger.info(
        "Pipeline summary — filtered:%d stale:%d dupes:%d bad_url:%d "
        "discord:%d gmail:%d",
        stats["filtered"], stats["stale"], stats["dupes"], stats["bad_url"],
        stats["discord"], stats["gmail"],
    )

    # ── 7. Persist to DB (all jobs that passed filters)
    all_approved = discord_queue + gmail_queue
    for job in all_approved:
        database.insert_job({
            "hash_id":     job["hash_id"],
            "job_title":   job.get("job_title", ""),
            "company":     job.get("company", ""),
            "location":    job.get("location", ""),
            "skills":      job.get("skills", ""),
            "source":      job.get("source", ""),
            "job_url":     job.get("job_url", ""),
            "posted_date": job.get("posted_date", ""),
            "posted_days": job.get("posted_days"),
            "score":       job.get("score", 0),
        })

    # ── 8. Notify
    overflow_gmail_count = len(gmail_queue)

    # Discord overflow: top 5 go to Discord, remainder to Gmail
    discord_overflow = discord_queue[DISCORD_MAX_JOBS:]
    gmail_queue = discord_overflow + gmail_queue   # merge overflow into Gmail

    if discord_queue:
        sent = discord_notifier.send_jobs(
            discord_queue,
            overflow_count=overflow_gmail_count + len(discord_overflow),
        )
        logger.info("Discord: %d/%d messages sent", sent, min(len(discord_queue), DISCORD_MAX_JOBS))
    else:
        logger.info("Discord: no new jobs to send")

    if gmail_queue:
        ok = gmail_notifier.send_digest(gmail_queue)
        logger.info("Gmail digest: %s (%d jobs)", "sent" if ok else "FAILED", len(gmail_queue))

    # Mark all as notified in DB
    for job in all_approved:
        database.mark_notified(job["hash_id"])

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("Cycle complete in %.1f seconds.", elapsed)
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Job Alert Bot")
    parser.add_argument(
        "--schedule", action="store_true",
        help=f"Run on a loop every {SCRAPE_INTERVAL_MINUTES} minutes"
    )
    args = parser.parse_args()

    database.init_db()

    if args.schedule:
        logger.info(
            "Scheduler mode: running every %d minutes.", SCRAPE_INTERVAL_MINUTES
        )
        while True:
            try:
                run_pipeline()
            except Exception as exc:
                logger.critical("Pipeline crashed: %s", exc, exc_info=True)
            logger.info("Sleeping %d minutes…", SCRAPE_INTERVAL_MINUTES)
            time.sleep(SCRAPE_INTERVAL_MINUTES * 60)
    else:
        run_pipeline()


if __name__ == "__main__":
    main()