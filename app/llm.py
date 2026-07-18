"""
Sends the scraped job page content to the Anthropic API (Claude Haiku 4.5)
and gets back clean, structured fields: company, position, location, pay.

Requires ANTHROPIC_API_KEY to be set in the environment. This is a normal
pay-as-you-go Anthropic API key from console.anthropic.com — NOT the same
thing as a Claude.ai Pro/Max subscription. Cost per parse is a small
fraction of a cent on Haiku 4.5.
"""

import json
import os
import re

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You extract structured data from job listing pages for a job \
application tracker. You will be given the page title, raw visible text, and \
(if available) structured JobPosting JSON-LD data from the page.

Respond with ONLY a JSON object and nothing else — no markdown fences, no \
preamble, no explanation. Exactly these keys:
{
  "company": string,   // company/organization name
  "position": string,  // job title
  "location": string,  // city/remote/hybrid info, keep it short
  "pay": string         // salary or pay range if listed, otherwise "Not listed"
}

Rules:
- If a field truly cannot be determined, use "Unknown" (or "Not listed" for pay).
- Keep location concise, e.g. "Remote", "Hybrid - New York, NY", "Austin, TX".
- Keep pay concise, e.g. "$120k-$150k", "$45/hr", "Not listed".
- Do not invent information that isn't present in the given content."""


def extract_job_fields(title: str, text: str, json_ld: dict | None) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Get a key from console.anthropic.com (separate from a Claude.ai subscription)."
        )

    user_content = f"PAGE TITLE:\n{title}\n\n"
    if json_ld:
        user_content += f"STRUCTURED JOB DATA (JSON-LD):\n{json.dumps(json_ld)[:3000]}\n\n"
    user_content += f"VISIBLE PAGE TEXT:\n{text}"

    payload = {
        "model": MODEL,
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_content}],
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    raw = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    raw = raw.strip()

    # Claude reliably follows "JSON only", but strip fences just in case.
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    parsed = json.loads(raw)

    return {
        "company": parsed.get("company", "Unknown"),
        "position": parsed.get("position", "Unknown"),
        "location": parsed.get("location", "Unknown"),
        "pay": parsed.get("pay", "Not listed"),
    }
