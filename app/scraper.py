"""
Fetches a job listing URL and extracts text for the LLM to parse.

Strategy:
1. Look for embedded schema.org JobPosting JSON-LD (many ATS platforms like
   Greenhouse, Lever, and Workday include this) — it's structured and reliable.
2. Always also grab the page title + visible text as a fallback / supplement,
   since JSON-LD isn't always present or complete (pay is often missing from it).
"""

import json
import re

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

MAX_TEXT_CHARS = 6000


def fetch_job_page(url: str) -> dict:
    """Returns {"title": str, "text": str, "json_ld": dict | None}."""
    with httpx.Client(follow_redirects=True, timeout=15.0, headers=HEADERS) as client:
        resp = client.get(url)
        resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    json_ld = _extract_job_posting_json_ld(soup)

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    text = text[:MAX_TEXT_CHARS]

    return {"title": title, "text": text, "json_ld": json_ld}


def _extract_job_posting_json_ld(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None
