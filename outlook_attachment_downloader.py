"""
Outlook Attachment Downloader & Excel Consolidator
===================================================
Uses win32com.client to connect to a local Outlook instance, downloads
Excel attachments from a specific sender, combines them into one
deduplicated table, and saves the result.

Prerequisites (run on Windows with Outlook installed):
    pip install pywin32 pandas openpyxl
"""

import os
from pathlib import Path
from datetime import datetime

import win32com.client
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

SENDER_EMAIL = "peter.vandeventer@thungela.com"

# If you have multiple Outlook accounts/mailboxes, set this to the mailbox
# you want to search.  Set to None to use the default mailbox.
TARGET_MAILBOX = "lion.steynberg@thungela.com"

# Excel parsing settings
HEADER_ROW = 2          # 0-indexed: row 3 in the file = index 2

# Output
OUTPUT_FILE = "consolidated_output.xlsx"
ATTACHMENT_DIR = "downloaded_attachments"

# ── Outlook COM helpers ──────────────────────────────────────────────────────


def get_inbox(target_mailbox: str | None = None):
    """
    Connect to Outlook via COM and return the Inbox folder.
    If target_mailbox is set, find that specific account's inbox.
    """
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")

    if target_mailbox:
        # Search through all accounts for the matching mailbox
        for store in namespace.Stores:
            if store.DisplayName.lower() == target_mailbox.lower():
                root = store.GetRootFolder()
                # Navigate to Inbox subfolder
                for folder in root.Folders:
                    if folder.Name.lower() == "inbox":
                        print(f"Using mailbox: {store.DisplayName}")
                        return folder
        # If exact match failed, try partial match on email
        for store in namespace.Stores:
            if target_mailbox.lower() in store.DisplayName.lower():
                root = store.GetRootFolder()
                for folder in root.Folders:
                    if folder.Name.lower() == "inbox":
                        print(f"Using mailbox: {store.DisplayName}")
                        return folder
        print(
            f"WARNING: Could not find mailbox '{target_mailbox}'. "
            f"Falling back to default Inbox."
        )

    # Default inbox
    inbox = namespace.GetDefaultFolder(6)  # 6 = olFolderInbox
    print(f"Using default Inbox: {inbox.Parent.Name}")
    return inbox


def get_messages_from_sender(inbox, sender_email: str) -> list:
    """
    Filter inbox for messages from the target sender that have attachments.
    Returns a list of (mail_item, received_datetime) tuples sorted oldest-first.
    """
    messages = inbox.Items
    # Restrict to the sender — DASL filter is most reliable for email address
    filter_str = (
        "@SQL=\"urn:schemas:httpmail:fromemail\" = "
        f"'{sender_email}'"
    )
    filtered = messages.Restrict(filter_str)

    results = []
    for i in range(filtered.Count, 0, -1):
        item = filtered.Item(i)
        if item.Attachments.Count > 0:
            results.append(item)

    # Sort oldest → newest so dedup keeps the newest
    results.sort(key=lambda m: m.ReceivedTime)

    print(f"Found {len(results)} message(s) from {sender_email} with attachments.")
    return results


def download_excel_attachments(messages: list) -> list[Path]:
    """Save all .xlsx/.xls attachments from the messages to disk."""
    os.makedirs(ATTACHMENT_DIR, exist_ok=True)
    downloaded = []

    for msg in messages:
        received_dt = msg.ReceivedTime
        # Format date for file prefix: YYYY-MM-DD
        date_prefix = received_dt.strftime("%Y-%m-%d")
        subject = msg.Subject or "no_subject"

        for j in range(1, msg.Attachments.Count + 1):
            att = msg.Attachments.Item(j)
            name = att.FileName

            if not name.lower().endswith((".xlsx", ".xls")):
                continue

            safe_name = f"{date_prefix}__{name}"
            dest = Path(ATTACHMENT_DIR) / safe_name
            att.SaveAsFile(str(dest.resolve()))
            downloaded.append(dest)
            print(f"  Downloaded: {dest}")

    print(f"Total Excel attachments downloaded: {len(downloaded)}")
    return downloaded


# ── Excel processing ─────────────────────────────────────────────────────────


def read_and_clean(filepath: Path) -> pd.DataFrame:
    """
    Read a single Excel file:
      - headers on row 3 (0-indexed row 2)
      - drop fully blank rows (up to 5 or more)
    """
    df = pd.read_excel(filepath, header=HEADER_ROW, engine="openpyxl")

    # Drop completely blank rows
    df.dropna(how="all", inplace=True)

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(
        lambda c: c.str.strip() if c.dtype == "object" else c
    )

    # Drop rows where every value is empty string after stripping
    df = df[~(df.astype(str).apply(lambda r: r.str.strip().eq("")).all(axis=1))]

    df.reset_index(drop=True, inplace=True)

    # Tag with source file so dedup can prefer newer files
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
    # Data columns = everything except our internal tag
    data_cols = [c for c in combined.columns if not c.startswith("_")]

    # Files are sorted by date prefix (oldest first), so keeping "last"
    # means the most recent version of a duplicated row is retained.
    combined.sort_values("_source_file", inplace=True)
    combined.drop_duplicates(subset=data_cols, keep="last", inplace=True)

    combined.drop(columns=["_source_file"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    print(f"Final shape after dedup:     {combined.shape}")
    return combined


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    print("=== Outlook Attachment Downloader & Consolidator ===\n")

    # 1. Connect to Outlook
    print("Connecting to Outlook...")
    inbox = get_inbox(TARGET_MAILBOX)

    # 2. Find emails from the sender
    print("\nSearching for messages...")
    messages = get_messages_from_sender(inbox, SENDER_EMAIL)

    if not messages:
        print("No messages found. Exiting.")
        return

    # 3. Download attachments
    print("\nDownloading attachments...")
    files = download_excel_attachments(messages)

    if not files:
        print("No Excel attachments found. Exiting.")
        return

    # 4. Consolidate into one table
    print("\nConsolidating Excel files...")
    result = consolidate(files)

    # 5. Save
    result.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")
    print(f"\nSaved consolidated table to: {OUTPUT_FILE}")
    print(f"  Rows: {len(result)}  |  Columns: {len(result.columns)}")


if __name__ == "__main__":
    main()
