#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Script to synchronize full-quality wallpapers (images & live wallpapers mp4)
from the @amandinhawallpaper Telegram group into the repository.
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    DocumentAttributeVideo,
    DocumentAttributeFilename,
)
from PIL import Image

try:
    import cv2  # OpenCV for extracting MP4 video thumbnail
except ImportError:
    cv2 = None

API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
STRING_SESSION = os.environ.get("TELEGRAM_STRING_SESSION", "")
CHANNEL_USERNAME = "amandinhawallpaper"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALLPAPERS_DIR = os.path.join(BASE_DIR, "wallpapers")
FULL_DIR = os.path.join(WALLPAPERS_DIR, "full")
THUMB_DIR = os.path.join(WALLPAPERS_DIR, "thumbnails")
CATALOG_PATH = os.path.join(WALLPAPERS_DIR, "catalog.json")

RAW_BASE_URL = "https://raw.githubusercontent.com/S-Marcos-S/viagara-wallpapers/main/wallpapers"

os.makedirs(FULL_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)


def generate_image_thumbnail(source_path: str, thumb_path: str, max_h: int = 720):
    try:
        with Image.open(source_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            thumb_w = int(w * (max_h / h))
            thumb = img.resize((thumb_w, max_h), Image.Resampling.LANCZOS)
            thumb.save(thumb_path, format="WEBP", quality=75, method=4)
        return True
    except Exception as e:
        print(f"Error generating image thumbnail: {e}")
        return False


def generate_video_thumbnail(video_path: str, thumb_path: str, max_h: int = 720):
    try:
        if cv2 is not None:
            cap = cv2.VideoCapture(video_path)
            success, frame = cap.read()
            cap.release()
            if success:
                # Convert BGR (OpenCV) to RGB (PIL)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                w, h = img.size
                thumb_w = int(w * (max_h / h))
                thumb = img.resize((thumb_w, max_h), Image.Resampling.LANCZOS)
                thumb.save(thumb_path, format="WEBP", quality=75, method=4)
                return True

        # Fallback using ffmpeg if installed
        res = os.system(f'ffmpeg -y -ss 00:00:00.500 -i "{video_path}" -vframes 1 -vf "scale=-1:{max_h}" "{thumb_path}" -loglevel quiet')
        return res == 0
    except Exception as e:
        print(f"Error generating video thumbnail: {e}")
        return False


async def main():
    if not API_ID or not API_HASH or not STRING_SESSION:
        print("Error: Missing TELEGRAM_API_ID, TELEGRAM_API_HASH, or TELEGRAM_STRING_SESSION environment variables.")
        sys.exit(1)

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

    existing_ids = {w["id"] for w in catalog.get("wallpapers", [])}

    print(f"Connecting to Telegram client...")
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    await client.start()

    print(f"Fetching entity for @{CHANNEL_USERNAME}...")
    entity = await client.get_entity(CHANNEL_USERNAME)

    print("Fetching messages from group...")
    new_items: List[Dict[str, Any]] = []

    # Iterate through recent messages (up to 300 per run)
    async for msg in client.iter_messages(entity, limit=300):
        if not msg.media:
            continue

        item_id = f"tg_{msg.id}"
        if item_id in existing_ids:
            continue

        media_type = None
        ext = None
        filename = None

        if isinstance(msg.media, MessageMediaPhoto):
            media_type = "image"
            ext = "jpg"
        elif isinstance(msg.media, MessageMediaDocument):
            doc = msg.media.document
            mime = doc.mime_type or ""
            
            # Check filename attribute
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                    break

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
                if "video" in mime or any(isinstance(a, DocumentAttributeVideo) for a in doc.attributes):
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

        print(f"Downloading message #{msg.id} ({media_type.upper()}: {full_filename})...")
        downloaded = await msg.download_media(file=full_path)
        if not downloaded or not os.path.exists(full_path):
            print(f"Failed to download media for message #{msg.id}")
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

        # Extract title from message text or caption if available
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
        }

        new_items.append(new_entry)
        existing_ids.add(item_id)
        print(f"Successfully processed: {title} ({media_type})")

    await client.disconnect()

    if not new_items:
        print("\nNo new wallpapers were found in the channel.")
        return

    # Prepend newest items so they show at the top
    catalog["wallpapers"] = new_items + catalog.get("wallpapers", [])

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nDone! Added {len(new_items)} new wallpapers to catalog.json.")


if __name__ == "__main__":
    asyncio.run(main())
