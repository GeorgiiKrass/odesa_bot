import os
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_NAME = os.getenv("GOOGLE_SHEETS_SPREADSHEET")
CREDS_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

client = None

try:
    creds_dict = json.loads(CREDS_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    print("Google Sheets connected")
except Exception as e:
    print("Google Sheets ERROR:", e)


def save_user(user_id, username, first_name):
    if not client:
        return

    try:
        sheet = client.open(SPREADSHEET_NAME).worksheet("users")
        sheet.append_row([
            user_id,
            username or "",
            first_name or "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
    except Exception as e:
        print("save_user error:", e)


def save_feedback(user_id, section, place_id, name, feedback):
    if not client:
        return

    try:
        sheet = client.open(SPREADSHEET_NAME).worksheet("place_feedback")
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id,
            section,
            place_id,
            name,
            feedback
        ])
    except Exception as e:
        print("save_feedback error:", e)
