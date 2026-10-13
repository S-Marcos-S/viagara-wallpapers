#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Script to backfill historical full-quality wallpapers from @amandinhawallpaper Telegram channel.
Allows downloading a customizable number of older wallpapers, strictly skipping posts from today,
and preventing any duplicate items (by message ID and content hash).
"""

import os
import sys
import json
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Set
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    MessageMediaDocument,
    DocumentAttributeVideo,
    DocumentAttributeFilename,
)
from PIL import Image

try:
    import cv2
except ImportError:
    cv2 = None

API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
STRING_SESSION = os.environ.get("TELEGRAM_STRING_SESSION", "")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "amandinhawallpaper")

TARGET_COUNT = int(os.environ.get("BACKFILL_COUNT", "30"))
SKIP_TODAY_RAW = os.environ.get("SKIP_TODAY", "true").lower()
SKIP_TODAY = SKIP_TODAY_RAW in ("true", "1", "yes", "y")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALLPAPERS_DIR = os.path.join(BASE_DIR, "wallpapers")
FULL_DIR = os.path.join(WALLPAPERS_DIR, "full")
THUMB_DIR = os.path.join(WALLPAPERS_DIR, "thumbnails")
CATALOG_PATH = os.path.join(WALLPAPERS_DIR, "catalog.json")

RAW_BASE_URL = "https://raw.githubusercontent.com/S-Marcos-S/viagara-wallpapers/main/wallpapers"

os.makedirs(FULL_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)


def calculate_file_md5(file_path: str) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_image_thumbnail(source_path: str, thumb_path: str, max_h: int = 1080) -> bool:
    try:
        with Image.open(source_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            thumb_w = int(w * (max_h / h))
            thumb = img.resize((thumb_w, max_h), Image.Resampling.LANCZOS)
            thumb.save(thumb_path, format="WEBP", quality=82, method=4)
        return True
    except Exception as e:
        print(f"Error generating image thumbnail: {e}")
        return False


def generate_video_thumbnail(video_path: str, thumb_path: str, max_h: int = 1080) -> bool:
    try:
        if cv2 is not None:
            cap = cv2.VideoCapture(video_path)
            success, frame = cap.read()
            cap.release()
            if success:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                w, h = img.size
                thumb_w = int(w * (max_h / h))
                thumb = img.resize((thumb_w, max_h), Image.Resampling.LANCZOS)
                thumb.save(thumb_path, format="WEBP", quality=82, method=4)
                return True

        res = os.system(
            f'ffmpeg -y -ss 00:00:00.500 -i "{video_path}" -vframes 1 -vf "scale=-1:{max_h}" "{thumb_path}" -loglevel quiet'
        )
        return res == 0
    except Exception as e:
        print(f"Error generating video thumbnail: {e}")
        return False


async def main():
    if not API_ID or not API_HASH or not STRING_SESSION:
        print("Error: Missing TELEGRAM_API_ID, TELEGRAM_API_HASH, or TELEGRAM_STRING_SESSION environment variables.")
        sys.exit(1)

    print(f"=== Viagara Wallpapers Historical Backfill ===")
    print(f"Target count: {TARGET_COUNT} wallpapers")
    print(f"Skip today's posts: {SKIP_TODAY}")
    print(f"Target channel: @{CHANNEL_USERNAME}")

    # Load existing catalog
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    else:
        catalog = {
            "version": 1,
            "categories": [
                {"id": "all", "label": "Todos"},
                {"id": "live", "label": "Live Wallpapers"},
                {"id": "images", "label": "Imagens"},
            ],
            "wallpapers": [],
        }

    existing_wallpapers = catalog.get("wallpapers", [])
    existing_ids: Set[str] = {w["id"] for w in existing_wallpapers}
    existing_hashes: Set[str] = {w.get("content_hash") for w in existing_wallpapers if w.get("content_hash")}

    print(f"Current catalog size: {len(existing_wallpapers)} wallpapers")

    today_utc = datetime.now(timezone.utc).date()
    print(f"Today UTC Date: {today_utc}")

    print("Connecting to Telegram client...")
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    await client.start()

    print(f"Resolving entity @{CHANNEL_USERNAME}...")
    entity = await client.get_entity(CHANNEL_USERNAME)

    new_items: List[Dict[str, Any]] = []
    scanned_messages = 0
    MAX_SCAN_LIMIT = 5000  # Scan up to 5000 messages back into history

    print(f"Scanning channel history (looking for {TARGET_COUNT} new uncataloged wallpapers)...")

    async for msg in client.iter_messages(entity, limit=MAX_SCAN_LIMIT):
        scanned_messages += 1

        if not msg.media or not isinstance(msg.media, MessageMediaDocument):
            continue

        item_id = f"tg_{msg.id}"
        if item_id in existing_ids:
            continue

        # Check date filter
        msg_date = msg.date
        if msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)
        msg_date_utc = msg_date.astimezone(timezone.utc).date()

        if SKIP_TODAY and msg_date_utc == today_utc:
            # Skip messages posted today
            continue

        doc = msg.media.document
        mime = doc.mime_type or ""
        doc_size = getattr(doc, "size", 0)

        filename = None
        has_video_attr = False
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name
            elif isinstance(attr, DocumentAttributeVideo):
                has_video_attr = True

        # Strictly ignore low-res stream previews
        if has_video_attr and (not filename or doc_size < 1_200_000):
            continue

        media_type = None
        ext = None
        if filename:
            lower_fn = filename.lower()
            if lower_fn.endswith((".jpg", ".jpeg")):
                media_type = "image"
                ext = "jpg"
            elif lower_fn.endswith(".png"):
                media_type = "image"
                ext = "png"
            elif lower_fn.endswith(".mp4"):
                media_type = "video"
                ext = "mp4"

        if not media_type:
            if "video" in mime or has_video_attr:
                if doc_size < 1_200_000:
                    continue
                media_type = "video"
                ext = "mp4"
            elif "image" in mime:
                media_type = "image"
                ext = "png" if "png" in mime else "jpg"

        if not media_type or not ext:
            continue

        full_filename = f"{item_id}.{ext}"
        thumb_filename = f"{item_id}.webp"
        full_path = os.path.join(FULL_DIR, full_filename)
        thumb_path = os.path.join(THUMB_DIR, thumb_filename)

        print(
            f"Downloading msg #{msg.id} [{msg_date_utc}] ({media_type.upper()}: {full_filename})..."
        )
        downloaded = await msg.download_media(file=full_path)
        if not downloaded or not os.path.exists(full_path):
            print(f"Failed to download media for msg #{msg.id}")
            continue

        # Check content hash to avoid duplicate files
        content_hash = calculate_file_md5(full_path)
        if content_hash in existing_hashes:
            print(f"Duplicate content detected by hash ({content_hash}). Skipping msg #{msg.id}")
            if os.path.exists(full_path):
                os.remove(full_path)
            continue

        # Generate thumbnail
        thumb_success = False
        if media_type == "image":
            thumb_success = generate_image_thumbnail(full_path, thumb_path)
        elif media_type == "video":
            thumb_success = generate_video_thumbnail(full_path, thumb_path)

        if not thumb_success:
            print(f"Failed to generate thumbnail for {full_filename}")
            if os.path.exists(full_path):
                os.remove(full_path)
            continue

        # Extract title from caption or fallback
        title = msg.text.strip().split("\n")[0] if msg.text else ""
        if not title or len(title) > 40:
            title = f"Live Wallpaper #{msg.id}" if media_type == "video" else f"Wallpaper #{msg.id}"

        new_entry = {
            "id": item_id,
            "name": title,
            "author": "Wallpaper HD/4K (Amanda)",
            "author_url": "https://t.me/amandinhawallpaper",
            "thumbnail_url": f"{RAW_BASE_URL}/thumbnails/{thumb_filename}",
            "full_url": f"{RAW_BASE_URL}/full/{full_filename}",
            "primary_color": "#121212",
            "category": "live" if media_type == "video" else "images",
            "type": media_type,
            "is_live": media_type == "video",
            "tags": ["live", "video"] if media_type == "video" else ["image", "hd", "4k"],
            "content_hash": content_hash,
        }

        new_items.append(new_entry)
        existing_ids.add(item_id)
        existing_hashes.add(content_hash)
        print(f" -> [{len(new_items)}/{TARGET_COUNT}] Processed: {title} ({media_type})")

        if len(new_items) >= TARGET_COUNT:
            print(f"Successfully reached target count ({TARGET_COUNT})! Halting history scan.")
            break

    await client.disconnect()

    if not new_items:
        print("\nNo new wallpapers were downloaded during this backfill run.")
        return

    # Combine with catalog and sort consistently by message ID (newest first)
    all_wallpapers = new_items + existing_wallpapers

    def get_sort_key(item: Dict[str, Any]) -> int:
        item_id = item.get("id", "")
        if item_id.startswith("tg_"):
            num_part = item_id[3:]
            if num_part.isdigit():
                return int(num_part)
        return 0

    all_wallpapers.sort(key=get_sort_key, reverse=True)
    catalog["wallpapers"] = all_wallpapers

    # Save newly added item IDs for priority classification
    new_ids = [item["id"] for item in new_items]
    tmp_path = os.path.join(BASE_DIR, "wallpapers", ".newly_added_ids.json")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(new_ids, f)
    except Exception as e:
        print(f"Notice: Could not write .newly_added_ids.json: {e}")

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone! Added {len(new_items)} new historical wallpapers to catalog.json.")
    print(f"Total catalog size is now: {len(all_wallpapers)} wallpapers.")


if __name__ == "__main__":
    asyncio.run(main())
