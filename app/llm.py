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

SYSTEM_PROMPT = """
You are an information extraction engine for software engineering job listings.

Your task is to extract structured fields from ONE job posting.

You will receive:
1. The page title.
2. Structured JobPosting JSON-LD (if available).
3. Raw visible page text.

Extraction priority:
1. JobPosting JSON-LD
2. Visible page text
3. Page title

If multiple sources disagree, prefer the higher priority source.

Return ONLY valid JSON.

Schema:
{
  "company": string,
  "position": string,
  "location": string,
  "pay": string
}

Rules:

Company
- Return the employer's official name.
- Never return the job board (LinkedIn, Greenhouse, Ashby, Workday, etc.).

Position
- Return the exact job title.
- Remove duplicate whitespace.
- Preserve level names such as I, II, III, Senior, Staff, Principal, Intern, New Grad.

Location
- Keep concise.
- Examples:
  "Remote"
  "Hybrid - New York, NY"
  "Austin, TX"
  "Mountain View, CA"
- If multiple locations are listed, join with " / ".
- If unknown, return "Unknown".

Pay
- Return exactly what is listed.
- Examples:
  "$120k-$150k"
  "$45/hr"
  "$130,000-$165,000"
- Search for phrases like "salary range" or "base pay" and return the first match.
- Examples:
  "Base pay: $120k-$150k"
  "Salary range: $120k-$150k"  
  "Hiring Min Rate: 71,808 USD" 
- If no compensation is listed, use best reasoning according to location, position, and company.
- If you make an estimate, return "Estimated".
- If you are 50 percent sure then return "Unknown".

General
- Never invent information.
- Ignore application instructions, benefits, equal opportunity statements, and company marketing.
- Ignore similar jobs, recommended jobs, advertisements, navigation links, and footer text.
- Extract information only for the primary job posting.
- Output ONLY the JSON object.
"""


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
