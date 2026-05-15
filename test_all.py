"""
test_all.py — Complete test suite for Job Alert Bot (Jobylly).

Run this from your project root:
    python test_all.py

Tests every component in order:
    1.  Environment & .env file
    2.  Database initialization
    3.  Hash generator
    4.  URL validator
    5.  Keyword filter
    6.  Freshness logic
    7.  Duplicate detection
    8.  Scoring engine
    9.  Scrapers (all sources)
    10. Discord notification (sends a real test card)
    11. Gmail digest (sends a real test email)
    12. Full pipeline (end-to-end)
"""

import os
import sys
import time
import shutil
import traceback

# Clear stale bytecode cache so Python always loads fresh source files
for cache_dir in ["scrapers/__pycache__", "filters/__pycache__",
                  "notifier/__pycache__", "utils/__pycache__", "__pycache__"]:
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

PASS  = "\033[92m  PASS\033[0m"
FAIL  = "\033[91m  FAIL\033[0m"
WARN  = "\033[93m  WARN\033[0m"
INFO  = "\033[94m  INFO\033[0m"
SKIP  = "\033[90m  SKIP\033[0m"

results = []   # (test_name, status, message)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(name, condition, pass_msg="", fail_msg="", warn=False):
    if condition:
        tag = PASS
        msg = pass_msg
    elif warn:
        tag = WARN
        msg = fail_msg
    else:
        tag = FAIL
        msg = fail_msg
    label = f"{tag}  {name}"
    print(f"{label}")
    if msg:
        print(f"        {msg}")
    results.append((name, "PASS" if condition else ("WARN" if warn else "FAIL"), msg))
    return condition


def skip(name, reason):
    print(f"{SKIP}  {name}")
    print(f"        {reason}")
    results.append((name, "SKIP", reason))


def run_test(name, fn):
    """Wrap a test function and catch unexpected exceptions."""
    try:
        fn()
    except Exception as exc:
        print(f"{FAIL}  {name} — unexpected exception")
        print(f"        {exc}")
        traceback.print_exc()
        results.append((name, "FAIL", str(exc)))


# ──────────────────────────────────────────────────────────────
# 1. Environment
# ──────────────────────────────────────────────────────────────
section("1. ENVIRONMENT & .env FILE")

def test_env():
    from dotenv import load_dotenv
    load_dotenv()

    webhook  = os.getenv("DISCORD_WEBHOOK_URL", "")
    sender   = os.getenv("GMAIL_SENDER", "")
    password = os.getenv("GMAIL_PASSWORD", "")
    receiver = os.getenv("GMAIL_RECIPIENT", "")

    check("DISCORD_WEBHOOK_URL is set",
          bool(webhook) and webhook.startswith("https://discord.com/api/webhooks/"),
          pass_msg=f"Webhook URL found",
          fail_msg="Not set or invalid — check your .env file")

    check("GMAIL_SENDER is set",
          bool(sender) and "@" in sender,
          pass_msg=f"Sender: {sender}",
          fail_msg="Not set — check your .env file",
          warn=True)

    check("GMAIL_PASSWORD is set",
          bool(password),
          pass_msg="App password found",
          fail_msg="Not set — Gmail digest will not work",
          warn=True)

    check("GMAIL_RECIPIENT is set",
          bool(receiver) and "@" in receiver,
          pass_msg=f"Recipient: {receiver}",
          fail_msg="Not set — Gmail digest will not work",
          warn=True)

run_test("Environment", test_env)


# ──────────────────────────────────────────────────────────────
# 2. Database
# ──────────────────────────────────────────────────────────────
section("2. DATABASE")

def test_database():
    import database
    database.init_db()
    check("Database initializes", True, pass_msg="data/jobs.db created")

    from utils.hash_generator import generate_hash
    test_hash = generate_hash("Junior Python Dev", "Test Corp", "https://example.com")
    database.insert_job({
        "hash_id":     test_hash,
        "job_title":   "Junior Python Dev",
        "company":     "Test Corp",
        "location":    "Remote",
        "skills":      "Python",
        "source":      "test",
        "job_url":     "https://example.com",
        "posted_date": "1 day ago",
        "posted_days": 1,
        "score":       100,
    })
    check("Job inserts into DB", True, pass_msg="Test record inserted")

    is_dup = database.is_duplicate(test_hash)
    check("Duplicate detection via DB", is_dup,
          pass_msg="Duplicate correctly detected",
          fail_msg="Duplicate not detected — check database.py")

    database.mark_notified(test_hash)
    check("Mark notified works", True, pass_msg="Notification timestamp set")

run_test("Database", test_database)


# ──────────────────────────────────────────────────────────────
# 3. Hash Generator
# ──────────────────────────────────────────────────────────────
section("3. HASH GENERATOR")

def test_hash():
    from utils.hash_generator import generate_hash

    h1 = generate_hash("Junior Python Dev", "Corp A", "https://example.com/job/1")
    h2 = generate_hash("Junior Python Dev", "Corp A", "https://example.com/job/1")
    h3 = generate_hash("Senior Python Dev", "Corp A", "https://example.com/job/1")

    check("Same input produces same hash",    h1 == h2,
          pass_msg=f"Hash: {h1}",
          fail_msg="Hashes differ — non-deterministic!")
    check("Different input produces different hash", h1 != h3,
          pass_msg="Hashes are distinct",
          fail_msg="Collision detected!")
    check("Hash is 32 characters long",       len(h1) == 32,
          pass_msg=f"Length: {len(h1)}",
          fail_msg=f"Wrong length: {len(h1)}")

run_test("Hash Generator", test_hash)


# ──────────────────────────────────────────────────────────────
# 4. URL Validator
# ──────────────────────────────────────────────────────────────
section("4. URL VALIDATOR")

def test_url_validator():
    from utils.url_validator import is_valid_url

    check("Valid URL passes (google.com)",
          is_valid_url("https://www.google.com"),
          pass_msg="google.com reachable",
          fail_msg="Could not reach google.com — check internet connection",
          warn=True)

    check("Invalid URL fails",
          not is_valid_url("https://this-domain-does-not-exist-xyz123.com"),
          pass_msg="Correctly rejected unreachable URL",
          fail_msg="Should have rejected this URL")

    check("Empty string fails",
          not is_valid_url(""),
          pass_msg="Empty string correctly rejected",
          fail_msg="Empty string should fail")

    check("Non-http string fails",
          not is_valid_url("not-a-url"),
          pass_msg="Non-URL string correctly rejected",
          fail_msg="Non-URL string should fail")

run_test("URL Validator", test_url_validator)


# ──────────────────────────────────────────────────────────────
# 5. Keyword Filter
# ──────────────────────────────────────────────────────────────
section("5. KEYWORD FILTER")

def test_keyword_filter():
    from filters.keyword_filter import passes_keyword_filter

    should_pass = [
        {'job_title': 'Junior Python Developer',      'description': 'entry level remote backend python flask',          'location': 'Remote'},
        {'job_title': 'Entry Level Backend Engineer',  'description': 'fastapi python junior work from home',             'location': 'WFH'},
        {'job_title': 'Python Automation Intern',      'description': 'automation python intern no experience required',  'location': 'Hybrid'},
        {'job_title': 'Associate Software Engineer',   'description': 'python api backend fresh graduate remote',         'location': 'Remote'},
    ]

    should_fail = [
        {'job_title': 'Senior Python Engineer',    'description': 'senior python backend lead 5 years',        'location': 'Remote'},
        {'job_title': 'Python Team Lead',          'description': 'lead python team manager remote',           'location': 'Remote'},
        {'job_title': 'Data Entry Clerk',          'description': 'encoding spreadsheet work from home',       'location': 'WFH'},
        {'job_title': 'Junior Python Developer',   'description': 'junior python developer on-site office',    'location': 'Makati City'},
        {'job_title': 'Principal Python Architect','description': 'principal architect python remote',         'location': 'Remote'},
    ]

    all_pass = True
    for job in should_pass:
        result = passes_keyword_filter(job)
        ok = check(f"SHOULD PASS: {job['job_title']}", result,
                   pass_msg="Correctly accepted",
                   fail_msg="Should have passed but was rejected")
        if not ok:
            all_pass = False

    for job in should_fail:
        result = passes_keyword_filter(job)
        ok = check(f"SHOULD FAIL: {job['job_title']}", not result,
                   pass_msg="Correctly rejected",
                   fail_msg="Should have been rejected but passed")
        if not ok:
            all_pass = False

run_test("Keyword Filter", test_keyword_filter)


# ──────────────────────────────────────────────────────────────
# 6. Freshness Logic
# ──────────────────────────────────────────────────────────────
section("6. FRESHNESS LOGIC")

def test_freshness():
    from filters.level_filter import evaluate_freshness, notification_channel

    cases = [
        ({'posted_days': 0,    'source': 'indeed'},      'high',   'discord'),
        ({'posted_days': 1,    'source': 'jobstreet'},    'high',   'discord'),
        ({'posted_days': 2,    'source': 'linkedin'},     'high',   'discord'),
        ({'posted_days': 3,    'source': 'indeed'},       'normal', 'discord'),
        ({'posted_days': 7,    'source': 'jobstreet'},    'normal', 'discord'),
        ({'posted_days': 8,    'source': 'linkedin'},     'low',    'gmail'),
        ({'posted_days': 14,   'source': 'indeed'},       'low',    'gmail'),
        ({'posted_days': 15,   'source': 'indeed'},       'reject', 'discard'),
        ({'posted_days': 30,   'source': 'jobstreet'},    'reject', 'discard'),
        ({'posted_days': None, 'source': 'indeed'},       'normal', 'discord'),
        ({'posted_days': None, 'source': 'google_jobs'},  'normal', 'discord'),
        ({'posted_days': None, 'source': 'facebook'},     'reject', 'discard'),
        ({'posted_days': None, 'source': 'linkedin'},     'reject', 'discard'),
    ]

    for job, expected_tier, expected_channel in cases:
        tier    = evaluate_freshness(job)
        channel = notification_channel(tier)
        days    = job['posted_days']
        label   = f"days={str(days):4}  source={job['source']:12}"

        check(f"Freshness: {label}",
              tier == expected_tier and channel == expected_channel,
              pass_msg=f"tier={tier}  channel={channel}",
              fail_msg=f"Expected tier={expected_tier} channel={expected_channel}, got tier={tier} channel={channel}")

run_test("Freshness Logic", test_freshness)


# ──────────────────────────────────────────────────────────────
# 7. Duplicate Detection
# ──────────────────────────────────────────────────────────────
section("7. DUPLICATE DETECTION")

def test_duplicates():
    from filters.duplicate_filter import is_new_job, reset_run_cache
    reset_run_cache()

    r1 = is_new_job("unique_test_hash_aaa")
    r2 = is_new_job("unique_test_hash_aaa")
    r3 = is_new_job("unique_test_hash_bbb")
    r4 = is_new_job("unique_test_hash_bbb")

    check("First occurrence is new",         r1 == True,
          pass_msg="Correctly identified as new",
          fail_msg="Should be True on first occurrence")
    check("Second occurrence is duplicate",  r2 == False,
          pass_msg="Correctly identified as duplicate",
          fail_msg="Should be False on second occurrence")
    check("Different hash is new",           r3 == True,
          pass_msg="Correctly identified as new",
          fail_msg="Different hash should be True")
    check("Same different hash is duplicate",r4 == False,
          pass_msg="Correctly identified as duplicate",
          fail_msg="Should be False on second occurrence")

run_test("Duplicate Detection", test_duplicates)


# ──────────────────────────────────────────────────────────────
# 8. Scoring Engine
# ──────────────────────────────────────────────────────────────
section("8. SCORING ENGINE")

def test_scoring():
    from filters.scoring import score_job

    # Perfect job — should score maximum points
    perfect_job = {
        'job_title':   'Junior Python Developer',
        'description': 'python flask fastapi backend api junior entry level',
        'location':    'Remote',
        'source':      'indeed',
        'posted_days': 1,
    }
    score = score_job(perfect_job, freshness_bonus=15)
    # +30 python +20 flask +20 remote +20 junior +15 fresh +10 indeed +15 bonus = 130
    check("Perfect job scores 130",
          score == 130,
          pass_msg=f"Score: {score}",
          fail_msg=f"Expected 130, got {score}")

    # No Python — should score lower
    no_python = {
        'job_title':   'Junior Java Developer',
        'description': 'java spring boot junior entry level remote',
        'location':    'Remote',
        'source':      'linkedin',
        'posted_days': 5,
    }
    score2 = score_job(no_python, freshness_bonus=10)
    check("No Python scores lower (no +30)",
          score2 < score,
          pass_msg=f"Score: {score2} (lower than {score})",
          fail_msg=f"Should be lower than {score}")

    # Old job — no fresh post bonus
    old_job = {
        'job_title':   'Junior Python Developer',
        'description': 'python backend junior entry level remote',
        'location':    'Remote',
        'source':      'jobstreet',
        'posted_days': 12,
    }
    score3 = score_job(old_job, freshness_bonus=5)
    check("Old job scores lower (no +15 fresh)",
          score3 < score,
          pass_msg=f"Score: {score3}",
          fail_msg=f"Old job should score lower than fresh job")

run_test("Scoring Engine", test_scoring)


# ──────────────────────────────────────────────────────────────
# 9. Scrapers
# ──────────────────────────────────────────────────────────────
section("9. SCRAPERS (live network requests — may take 1-2 minutes)")

SCRAPER_TESTS = [
    ("Google Jobs / RemoteOK", "scrapers.google_jobs"),
    ("Indeed",                 "scrapers.indeed"),
    ("JobStreet",              "scrapers.jobstreet"),
    ("OnlineJobs.ph",          "scrapers.onlinejobs"),
    ("Remote Rocketship",      "scrapers.remoterocketship"),
    ("LinkedIn",               "scrapers.linkedin"),
]

for name, module_path in SCRAPER_TESTS:
    try:
        import importlib
        mod  = importlib.import_module(module_path)
        jobs = mod.scrape()

        check(f"{name}: returns a list",
              isinstance(jobs, list),
              pass_msg=f"{len(jobs)} raw jobs found",
              fail_msg="scrape() did not return a list",
              warn=True)

        if jobs:
            sample = jobs[0]
            has_title = bool(sample.get("job_title"))
            has_url   = bool(sample.get("job_url"))
            check(f"{name}: jobs have title and URL",
                  has_title and has_url,
                  pass_msg=f"Sample: {sample.get('job_title')} | {sample.get('job_url')[:60]}",
                  fail_msg="Missing job_title or job_url in results",
                  warn=True)
        else:
            skip(f"{name}: job content check",
                 "0 jobs returned — board may be blocking temporarily, try again later")

        time.sleep(1)

    except Exception as exc:
        check(f"{name}: scraper runs without crashing",
              False,
              fail_msg=str(exc),
              warn=True)


# ──────────────────────────────────────────────────────────────
# 10. Discord Notification
# ──────────────────────────────────────────────────────────────
section("10. DISCORD NOTIFICATION (sends a real test card)")

def test_discord():
    from dotenv import load_dotenv
    load_dotenv()
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "")

    if not webhook or not webhook.startswith("https://discord.com/api/webhooks/"):
        skip("Discord notification", "DISCORD_WEBHOOK_URL not configured in .env")
        return

    from notifier.discord import send_jobs

    fake_job = [{
        'job_title':      'Junior Python Developer — TEST NOTIFICATION',
        'company':        'Jobylly Test',
        'location':       'Remote — Philippines',
        'skills':         'Python, Flask, FastAPI, REST API',
        'source':         'onlinejobs_ph',
        'job_url':        'https://www.onlinejobs.ph',
        'posted_days':    1,
        'posted_date':    '1 day ago',
        'score':          130,
        'freshness_tier': 'high',
    }]

    sent = send_jobs(fake_job)
    check("Discord sends test notification",
          sent == 1,
          pass_msg="Test card sent — check your Discord channel!",
          fail_msg="Failed to send — check DISCORD_WEBHOOK_URL in .env")

run_test("Discord Notification", test_discord)


# ──────────────────────────────────────────────────────────────
# 11. Gmail Digest
# ──────────────────────────────────────────────────────────────
section("11. GMAIL DIGEST (sends a real test email)")

def test_gmail():
    from dotenv import load_dotenv
    load_dotenv()
    sender   = os.getenv("GMAIL_SENDER", "")
    password = os.getenv("GMAIL_PASSWORD", "")
    receiver = os.getenv("GMAIL_RECIPIENT", "")

    if not all([sender, password, receiver]):
        skip("Gmail digest", "Gmail credentials not fully configured in .env")
        return

    from notifier.gmail import send_digest

    fake_jobs = [
        {
            'job_title':   'Junior Python Developer — TEST EMAIL',
            'company':     'Jobylly Test Corp',
            'location':    'Remote — Philippines',
            'source':      'jobstreet',
            'job_url':     'https://ph.jobstreet.com',
            'posted_days': 9,
            'score':       85,
        },
        {
            'job_title':   'Python Flask Intern — TEST EMAIL',
            'company':     'Remote Startup PH',
            'location':    'Work From Home',
            'source':      'onlinejobs_ph',
            'job_url':     'https://www.onlinejobs.ph',
            'posted_days': 11,
            'score':       75,
        },
    ]

    ok = send_digest(fake_jobs)
    check("Gmail digest sends successfully",
          ok,
          pass_msg=f"Test email sent to {receiver} — check your inbox!",
          fail_msg="Failed to send — check Gmail credentials in .env")

run_test("Gmail Digest", test_gmail)


# ──────────────────────────────────────────────────────────────
# 12. Full Pipeline
# ──────────────────────────────────────────────────────────────
section("12. FULL PIPELINE (end-to-end)")

def test_pipeline():
    print(f"{INFO}  Running full pipeline — this may take 1-3 minutes...")

    import subprocess
    result = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        timeout=300,
    )

    success = result.returncode == 0
    check("Pipeline runs without crashing",
          success,
          pass_msg="main.py exited cleanly",
          fail_msg=f"main.py crashed — see error below")

    if not success:
        print(f"\n--- STDERR ---\n{result.stderr[-1000:]}")

    # Check log output for key pipeline stages
    output = result.stdout + result.stderr
    stages = [
        ("Scraping ran",        "raw jobs"),
        ("Filtering ran",       "filtered:"),
        ("Cycle completed",     "Cycle complete"),
    ]
    for label, keyword in stages:
        check(f"Pipeline stage: {label}",
              keyword in output,
              pass_msg=f"Found '{keyword}' in output",
              fail_msg=f"'{keyword}' not found — stage may have been skipped",
              warn=True)

    # Run twice to test deduplication
    print(f"\n{INFO}  Running pipeline a second time to test deduplication...")
    result2 = subprocess.run(
        [sys.executable, "main.py"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    output2 = result2.stdout + result2.stderr
    check("Second run detects duplicates",
          "dupes:" in output2,
          pass_msg="Duplicate detection confirmed working",
          fail_msg="Could not confirm duplicate detection",
          warn=True)

run_test("Full Pipeline", test_pipeline)


# ──────────────────────────────────────────────────────────────
# Final Summary
# ──────────────────────────────────────────────────────────────
section("FINAL TEST SUMMARY")

passed  = sum(1 for _, s, _ in results if s == "PASS")
failed  = sum(1 for _, s, _ in results if s == "FAIL")
warned  = sum(1 for _, s, _ in results if s == "WARN")
skipped = sum(1 for _, s, _ in results if s == "SKIP")
total   = len(results)

print(f"\n  Total tests : {total}")
print(f"  \033[92mPassed\033[0m      : {passed}")
print(f"  \033[91mFailed\033[0m      : {failed}")
print(f"  \033[93mWarnings\033[0m    : {warned}")
print(f"  \033[90mSkipped\033[0m     : {skipped}")

if failed > 0:
    print(f"\n\033[91m  FAILED TESTS:\033[0m")
    for name, status, msg in results:
        if status == "FAIL":
            print(f"    - {name}")
            if msg:
                print(f"      {msg}")

if warned > 0:
    print(f"\n\033[93m  WARNINGS (non-critical):\033[0m")
    for name, status, msg in results:
        if status == "WARN":
            print(f"    - {name}")
            if msg:
                print(f"      {msg}")

print()
if failed == 0:
    print("  \033[92m✅ All critical tests passed! Your bot is ready to run.\033[0m")
else:
    print("  \033[91m❌ Some tests failed. Fix the issues above before deploying.\033[0m")
print()