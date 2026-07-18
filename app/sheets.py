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
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"GOOGLE_CREDENTIALS_JSON isn't valid JSON ({e}). "
            "Make sure you copied the ENTIRE .json file contents, unmodified."
        ) from e

    try:
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception as e:
        raise RuntimeError(f"GOOGLE_CREDENTIALS_JSON couldn't be loaded as credentials: {e}") from e


def _get_sheet():
    sheet_id = os.environ.get("SHEET_ID")
    sheet_tab = os.environ.get("SHEET_TAB", "Sheet1")
    if not sheet_id:
        raise RuntimeError("SHEET_ID environment variable is not set.")

    creds = _get_credentials()
    client = gspread.authorize(creds)

    try:
        spreadsheet = client.open_by_key(sheet_id)
    except gspread.exceptions.SpreadsheetNotFound as e:
        raise RuntimeError(
            f"No spreadsheet found for SHEET_ID='{sheet_id}'. Check the ID is correct, "
            "and that the service account email has been shared as an Editor on this sheet."
        ) from e
    except gspread.exceptions.APIError as e:
        raise RuntimeError(f"Google Sheets API error opening the spreadsheet: {e}") from e

    try:
        return spreadsheet.worksheet(sheet_tab)
    except gspread.exceptions.WorksheetNotFound as e:
        raise RuntimeError(
            f"No tab named '{sheet_tab}' in this spreadsheet. Check SHEET_TAB matches the "
            "exact tab name (case-sensitive)."
        ) from e


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