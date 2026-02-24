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

# Outlook folder path — each level separated by a backslash.
# This maps to: \\lion.steynberg@Thungela.com\ASR Department\Peter Van Devenenter
MAILBOX_NAME = "lion.steynberg@Thungela.com"
FOLDER_PATH = ["ASR Department", "Peter Van Devenenter"]

# Excel parsing settings
HEADER_ROW = 2          # 0-indexed: row 3 in the file = index 2

# Output
OUTPUT_FILE = "consolidated_output.xlsx"
ATTACHMENT_DIR = "downloaded_attachments"

# ── Outlook COM helpers ──────────────────────────────────────────────────────


def get_target_folder(mailbox_name: str, folder_path: list[str]):
    """
    Connect to Outlook via COM and navigate to a specific folder.
    E.g. mailbox_name="lion.steynberg@Thungela.com",
         folder_path=["ASR Department", "Peter Van Devenenter"]
    navigates to \\lion.steynberg@Thungela.com\ASR Department\Peter Van Devenenter
    """
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")

    # Find the mailbox store (case-insensitive)
    root = None
    for store in namespace.Stores:
        if store.DisplayName.lower() == mailbox_name.lower():
            root = store.GetRootFolder()
            print(f"Found mailbox: {store.DisplayName}")
            break

    if root is None:
        # Try partial match
        for store in namespace.Stores:
            if mailbox_name.lower() in store.DisplayName.lower():
                root = store.GetRootFolder()
                print(f"Found mailbox (partial match): {store.DisplayName}")
                break

    if root is None:
        available = [s.DisplayName for s in namespace.Stores]
        raise RuntimeError(
            f"Could not find mailbox '{mailbox_name}'.\n"
            f"Available stores: {available}"
        )

    # Walk down the subfolder path
    current = root
    for subfolder_name in folder_path:
        found = False
        for folder in current.Folders:
            if folder.Name.lower() == subfolder_name.lower():
                current = folder
                found = True
                break
        if not found:
            available = [f.Name for f in current.Folders]
            raise RuntimeError(
                f"Could not find subfolder '{subfolder_name}' "
                f"inside '{current.Name}'.\n"
                f"Available subfolders: {available}"
            )

    print(f"Using folder: {current.FolderPath}")
    return current


def get_messages_with_attachments(folder) -> list:
    """
    Get all messages in the folder that have attachments.
    Returns a list sorted oldest-first so dedup keeps the newest.
    """
    messages = folder.Items
    results = []

    for i in range(messages.Count, 0, -1):
        item = messages.Item(i)
        if item.Attachments.Count > 0:
            results.append(item)

    # Sort oldest → newest so dedup keeps the newest
    results.sort(key=lambda m: m.ReceivedTime)

    print(f"Found {len(results)} message(s) with attachments in folder.")
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

    # 1. Connect to Outlook and navigate to the target folder
    print("Connecting to Outlook...")
    folder = get_target_folder(MAILBOX_NAME, FOLDER_PATH)

    # 2. Find emails with attachments in the folder
    print("\nSearching for messages...")
    messages = get_messages_with_attachments(folder)

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
