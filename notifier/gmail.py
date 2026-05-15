"""
notifier/gmail.py — Gmail SMTP digest sender.

Sends an HTML email grouped by source when overflow occurs (8-14 day jobs
or when Discord limit is exceeded).
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import GMAIL_SENDER, GMAIL_PASSWORD, GMAIL_RECIPIENT

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def _group_by_source(jobs: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for job in jobs:
        src = job.get("source", "Unknown")
        grouped.setdefault(src, []).append(job)
    return grouped


def _build_html(jobs: list[dict]) -> str:
    grouped = _group_by_source(jobs)
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows = ""
    for source, source_jobs in grouped.items():
        rows += f"""
        <tr>
          <td colspan="4"
              style="background:#1a1a2e;color:#e0e0e0;padding:10px 16px;
                     font-weight:bold;font-size:15px;border-radius:4px;">
            📌 {source.replace('_',' ').title()}
          </td>
        </tr>"""
        for job in source_jobs:
            days_raw = job.get("posted_days")
            posted   = (
                "Today" if days_raw == 0 else
                "Yesterday" if days_raw == 1 else
                f"{days_raw}d ago" if days_raw is not None else
                job.get("posted_date", "Unknown")
            )
            rows += f"""
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid #2a2a4a;">
            <a href="{job.get('job_url','#')}"
               style="color:#7b68ee;font-weight:600;text-decoration:none;">
              {job.get('job_title','N/A')}
            </a>
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid #2a2a4a;color:#b0b0c0;">
            {job.get('company','N/A')}
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid #2a2a4a;color:#b0b0c0;">
            {job.get('location','Remote')}
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid #2a2a4a;color:#888;font-size:12px;">
            {posted} · Score {job.get('score',0)}
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Python Job Alert Digest</title>
</head>
<body style="margin:0;padding:0;background:#0d0d1a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="max-width:700px;margin:30px auto;background:#12122a;
                border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.5);">
    <tr>
      <td style="background:linear-gradient(135deg,#1a1a4e,#2d1b69);
                 padding:28px 32px;text-align:center;">
        <h1 style="color:#e0d7ff;margin:0;font-size:24px;letter-spacing:1px;">
          🐍 PYTHON JOB ALERT DIGEST
        </h1>
        <p style="color:#a090d0;margin:6px 0 0;font-size:13px;">{now}</p>
      </td>
    </tr>
    <tr>
      <td style="padding:8px 0;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <thead>
            <tr style="background:#1e1e3a;">
              <th style="padding:10px 16px;text-align:left;color:#9090b0;font-size:12px;
                         text-transform:uppercase;letter-spacing:.5px;">Position</th>
              <th style="padding:10px 16px;text-align:left;color:#9090b0;font-size:12px;
                         text-transform:uppercase;letter-spacing:.5px;">Company</th>
              <th style="padding:10px 16px;text-align:left;color:#9090b0;font-size:12px;
                         text-transform:uppercase;letter-spacing:.5px;">Location</th>
              <th style="padding:10px 16px;text-align:left;color:#9090b0;font-size:12px;
                         text-transform:uppercase;letter-spacing:.5px;">Posted</th>
            </tr>
          </thead>
          <tbody style="color:#d0d0e0;">{rows}</tbody>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 32px;text-align:center;color:#5a5a7a;font-size:12px;
                 border-top:1px solid #2a2a4a;">
        JobAlertBot · Automated digest · Python jobs only
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


def send_digest(jobs: list[dict]) -> bool:
    """
    Send an HTML email digest of the given jobs.
    Returns True on success.
    """
    if not jobs:
        logger.info("Gmail digest: no jobs to send.")
        return True

    if not all([GMAIL_SENDER, GMAIL_PASSWORD, GMAIL_RECIPIENT]):
        logger.error("Gmail credentials not fully configured.")
        return False

    subject = f"🐍 Python Job Digest — {len(jobs)} job{'s' if len(jobs) != 1 else ''} found"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_SENDER
    msg["To"]      = GMAIL_RECIPIENT

    # Plain text fallback
    plain = "PYTHON JOB ALERT DIGEST\n\n"
    for job in jobs:
        plain += (
            f"{job.get('job_title','N/A')}\n"
            f"Company: {job.get('company','N/A')}\n"
            f"Source:  {job.get('source','N/A')}\n"
            f"Link:    {job.get('job_url','N/A')}\n\n"
        )

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_html(jobs), "html"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, GMAIL_RECIPIENT, msg.as_string())
        logger.info("Gmail digest sent: %d jobs → %s", len(jobs), GMAIL_RECIPIENT)
        return True
    except smtplib.SMTPException as exc:
        logger.error("Gmail send error: %s", exc)
        return False