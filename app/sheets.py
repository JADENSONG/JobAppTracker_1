"""
Google Sheets logging — adapted from the original job_tracker.py script.

Instead of a local credentials file path, this reads the service account
JSON straight out of an environment variable (GOOGLE_CREDENTIALS_JSON),
which is how you'll provide it once this is deployed (Render/Railway/etc.
let you paste multi-line secrets into env vars).
"""

import json
import os
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = ["Company", "Position", "Location", "Date Applied", "Status", "Pay", "Link"]


def _get_credentials() -> Credentials:
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not raw:
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_JSON environment variable is not set. "
            "Paste the full contents of your service account JSON file into it."
        )
    info = json.loads(raw)
    return Credentials.from_service_account_info(info, scopes=SCOPES)


def _get_sheet():
    sheet_id = os.environ.get("SHEET_ID")
    sheet_tab = os.environ.get("SHEET_TAB", "Sheet1")
    if not sheet_id:
        raise RuntimeError("SHEET_ID environment variable is not set.")

    creds = _get_credentials()
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id).worksheet(sheet_tab)


def _ensure_headers(sheet):
    first_row = sheet.row_values(1)
    if not first_row:
        sheet.append_row(HEADERS, value_input_option="RAW")


def add_application(company: str, position: str, location: str, pay: str, link: str) -> dict:
    """Append one row to the tracker sheet. Returns the row that was written."""
    today = date.today().strftime("%m-%d-%Y")
    status = "Waiting"

    row = [
        company or "Unknown",
        position or "Unknown",
        location or "Unknown",
        today,
        status,
        pay or "Not listed",
        f'=HYPERLINK("{link}", "Apply")',
    ]

    sheet = _get_sheet()
    _ensure_headers(sheet)
    sheet.append_row(row, value_input_option="USER_ENTERED")

    return {
        "company": row[0],
        "position": row[1],
        "location": row[2],
        "date": row[3],
        "status": row[4],
        "pay": row[5],
        "link": link,
    }
