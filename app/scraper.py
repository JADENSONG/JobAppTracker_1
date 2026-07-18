"""
Fetches a job listing URL and extracts text for the LLM to parse.

Strategy:
1. Look for embedded schema.org JobPosting JSON-LD (many ATS platforms like
   Greenhouse, Lever, and Workday include this) — it's structured and reliable.
2. Grab the page title + visible text as a fallback / supplement, since
   JSON-LD isn't always present or complete (pay is often missing from it).
3. Some career sites (Dayforce/Ceridian, some Workday boards, and other
   single-page-app style ATSs) render the actual job content with
   JavaScript — a plain HTTP fetch only sees an empty page shell. When that's
   detected (suspiciously little text), fall back to a rendering proxy
   (Jina AI Reader) that runs a real headless browser and returns the fully
   rendered page as clean text.
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
THIN_CONTENT_THRESHOLD = 400  # chars — below this, assume JS didn't render and try the fallback

READER_URL = "https://r.jina.ai/"


def fetch_job_page(url: str) -> dict:
    """Returns {"title": str, "text": str, "json_ld": dict | None}."""
    title, text, json_ld = _fetch_static(url)

    if not json_ld and len(text) < THIN_CONTENT_THRESHOLD:
        try:
            rendered_text = _fetch_rendered(url)
        except Exception:
            rendered_text = ""

        if len(rendered_text) > len(text):
            text = rendered_text[:MAX_TEXT_CHARS]

    return {"title": title, "text": text, "json_ld": json_ld}


def _fetch_static(url: str) -> tuple[str, str, dict | None]:
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

    return title, text, json_ld


def _fetch_rendered(url: str) -> str:
    """Fetch a JS-rendered version of the page via Jina AI Reader
    (free, no key required for light/personal use — see r.jina.ai)."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{READER_URL}{url}")
        resp.raise_for_status()
    return resp.text.strip()


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