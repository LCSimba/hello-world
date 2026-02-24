"""
Outlook Attachment Downloader & Excel Consolidator
===================================================
Downloads Excel attachments from a specific sender via Microsoft Graph API,
combines them into one deduplicated table, and saves the result.

Prerequisites:
    pip install msal requests pandas openpyxl

Setup:
    1. Register an app in Azure AD (portal.azure.com > App registrations).
    2. Set a **Mobile/Desktop** redirect URI to http://localhost .
    3. Under API Permissions, add Microsoft Graph > Delegated:
         - Mail.Read
    4. Copy your Application (client) ID and Tenant ID into the config below.
"""

import os
import tempfile
from pathlib import Path

import msal
import requests
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

# Azure AD app registration details — fill these in
CLIENT_ID = "YOUR_CLIENT_ID"           # Application (client) ID
TENANT_ID = "YOUR_TENANT_ID"           # Directory (tenant) ID
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

# Microsoft Graph scopes
SCOPES = ["Mail.Read"]

# Mail filter settings
MAILBOX_USER = "lion.steynberg@thungela.com"  # your mailbox
SENDER_EMAIL = "peter.vandeventer@thungela.com"

# Excel parsing settings
HEADER_ROW = 2          # 0-indexed: row 3 in the file = index 2
MAX_BLANK_ROWS = 5      # blank rows to expect and remove

# Output
OUTPUT_FILE = "consolidated_output.xlsx"
ATTACHMENT_DIR = "downloaded_attachments"

# ── Authentication ───────────────────────────────────────────────────────────

def get_access_token() -> str:
    """Authenticate interactively via browser and return an access token."""

    # Token cache so you don't re-auth every run
    cache = msal.SerializableTokenCache()
    cache_file = Path(".token_cache.bin")
    if cache_file.exists():
        cache.deserialize(cache_file.read_text())

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )

    # Try silent token acquisition first
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    # Fall back to interactive browser login
    if not result:
        result = app.acquire_token_interactive(scopes=SCOPES)

    # Persist cache
    if cache.has_state_changed:
        cache_file.write_text(cache.serialize())

    if "access_token" not in result:
        raise RuntimeError(
            f"Authentication failed: {result.get('error_description', result)}"
        )

    return result["access_token"]


# ── Graph API helpers ────────────────────────────────────────────────────────

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_messages_from_sender(token: str) -> list[dict]:
    """Fetch all messages from the target sender that have attachments."""

    headers = {"Authorization": f"Bearer {token}"}
    messages = []
    # Filter: from the sender AND has attachments AND attachment is xlsx/xls
    filter_query = (
        f"from/emailAddress/address eq '{SENDER_EMAIL}' "
        f"and hasAttachments eq true"
    )
    url = (
        f"{GRAPH_BASE}/me/messages"
        f"?$filter={filter_query}"
        f"&$select=id,subject,receivedDateTime,hasAttachments"
        f"&$orderby=receivedDateTime desc"
        f"&$top=100"
    )

    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        messages.extend(data.get("value", []))
        url = data.get("@odata.nextLink")  # pagination

    print(f"Found {len(messages)} message(s) from {SENDER_EMAIL} with attachments.")
    return messages


def download_excel_attachments(token: str, messages: list[dict]) -> list[Path]:
    """Download all .xlsx/.xls attachments and return their local paths."""

    headers = {"Authorization": f"Bearer {token}"}
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)
    downloaded = []

    for msg in messages:
        msg_id = msg["id"]
        received = msg["receivedDateTime"]
        subject = msg.get("subject", "no_subject")

        att_url = f"{GRAPH_BASE}/me/messages/{msg_id}/attachments"
        resp = requests.get(att_url, headers=headers, timeout=30)
        resp.raise_for_status()

        for att in resp.json().get("value", []):
            name = att.get("name", "")
            if not name.lower().endswith((".xlsx", ".xls")):
                continue

            # Prefix with date for traceability
            safe_date = received[:10]
            safe_name = f"{safe_date}__{name}"
            dest = Path(ATTACHMENT_DIR) / safe_name

            # Write the attachment bytes
            import base64
            content_bytes = base64.b64decode(att["contentBytes"])
            dest.write_bytes(content_bytes)
            downloaded.append(dest)
            print(f"  Downloaded: {dest}")

    print(f"Total Excel attachments downloaded: {len(downloaded)}")
    return downloaded


# ── Excel processing ─────────────────────────────────────────────────────────

def read_and_clean(filepath: Path) -> pd.DataFrame:
    """
    Read a single Excel file with:
      - headers on row 3 (0-indexed row 2)
      - up to 5 blank rows removed
    """
    df = pd.read_excel(filepath, header=HEADER_ROW, engine="openpyxl")

    # Drop completely blank rows
    df.dropna(how="all", inplace=True)

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda c: c.str.strip() if c.dtype == "object" else c)

    # Drop rows where every value is empty string after stripping
    df = df[~(df.astype(str).apply(lambda r: r.str.strip().eq("")).all(axis=1))]

    df.reset_index(drop=True, inplace=True)

    # Tag with source file for debugging
    df["_source_file"] = filepath.name

    return df


def consolidate(files: list[Path]) -> pd.DataFrame:
    """Read all files, concatenate, and deduplicate keeping the most recent."""

    frames = []
    for f in sorted(files):
        try:
            df = read_and_clean(f)
            print(f"  Parsed {f.name}: {len(df)} rows, {len(df.columns)} cols")
            frames.append(df)
        except Exception as exc:
            print(f"  WARNING: Could not parse {f.name}: {exc}")

    if not frames:
        raise RuntimeError("No valid Excel files could be parsed.")

    combined = pd.concat(frames, ignore_index=True)
    print(f"\nCombined shape before dedup: {combined.shape}")

    # ── Deduplication ────────────────────────────────────────────────────
    # Strategy: identify the "real" data columns (exclude our metadata col),
    # then drop duplicates keeping the LAST occurrence.  Because files are
    # sorted by date prefix (oldest first), the last occurrence = most recent.
    data_cols = [c for c in combined.columns if not c.startswith("_")]

    combined.sort_values("_source_file", inplace=True)  # oldest file first
    combined.drop_duplicates(subset=data_cols, keep="last", inplace=True)

    combined.drop(columns=["_source_file"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    print(f"Final shape after dedup:     {combined.shape}")
    return combined


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Outlook Attachment Downloader & Consolidator ===\n")

    # 1. Authenticate
    print("Authenticating...")
    token = get_access_token()

    # 2. Fetch messages
    print("\nFetching messages...")
    messages = get_messages_from_sender(token)

    if not messages:
        print("No messages found. Exiting.")
        return

    # 3. Download attachments
    print("\nDownloading attachments...")
    files = download_excel_attachments(token, messages)

    if not files:
        print("No Excel attachments found. Exiting.")
        return

    # 4. Consolidate
    print("\nConsolidating Excel files...")
    result = consolidate(files)

    # 5. Save
    result.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")
    print(f"\nSaved consolidated table to: {OUTPUT_FILE}")
    print(f"  Rows: {len(result)}  |  Columns: {len(result.columns)}")


if __name__ == "__main__":
    main()
