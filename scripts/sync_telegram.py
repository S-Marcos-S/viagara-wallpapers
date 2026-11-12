#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Script to synchronize full-quality wallpapers (images & live wallpapers mp4)
from the @amandinhawallpaper Telegram group into the repository.

Features:
- Robust deduplication:
  1. Telegram message ID check (tg_<id>).
  2. Cryptographic content hash (MD5) check to avoid reposts and duplicates.
  3. Video preview / low-res filter (< 1.2 MB stream video discarded).
  4. Automatic calculation & population of content_hash for existing catalog entries.
- Automated Historical Fallback (Backfill):
  When no new wallpapers are found in recent messages, it automatically searches
  the channel's past history for wallpapers that are not yet in the repository,
  using a persistent historical cursor (backfill_cursor_id) that advances backwards.
"""

import os
import sys
import json
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Set
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
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
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "amandinhawallpaper")

RECENT_SCAN_LIMIT = int(os.environ.get("RECENT_SCAN_LIMIT", "300"))
FALLBACK_BACKFILL_COUNT = int(os.environ.get("FALLBACK_BACKFILL_COUNT", "15"))
ENABLE_FALLBACK_BACKFILL = os.environ.get("ENABLE_FALLBACK_BACKFILL", "true").lower() in ("true", "1", "yes", "y")
HISTORICAL_SCAN_LIMIT = int(os.environ.get("HISTORICAL_SCAN_LIMIT", "3000"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALLPAPERS_DIR = os.path.join(BASE_DIR, "wallpapers")
FULL_DIR = os.path.join(WALLPAPERS_DIR, "full")
THUMB_DIR = os.path.join(WALLPAPERS_DIR, "thumbnails")
CATALOG_PATH = os.path.join(WALLPAPERS_DIR, "catalog.json")

RAW_BASE_URL = "https://raw.githubusercontent.com/S-Marcos-S/viagara-wallpapers/main/wallpapers"

os.makedirs(FULL_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)


def calculate_file_md5(file_path: str) -> str:
    """Calculate MD5 hash of a local file in 64KB chunks."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def populate_missing_hashes(catalog: Dict[str, Any]) -> int:
    """Populates content_hash for catalog items if the file is available in FULL_DIR."""
    populated = 0
    for item in catalog.get("wallpapers", []):
        if item.get("content_hash"):
            continue
        item_id = item.get("id", "")
        if not item_id:
            continue
        for ext in ("jpg", "png", "mp4", "jpeg"):
            path = os.path.join(FULL_DIR, f"{item_id}.{ext}")
            if os.path.exists(path):
                try:
                    ch = calculate_file_md5(path)
                    item["content_hash"] = ch
                    populated += 1
                except Exception as e:
                    print(f"Warning: could not calculate hash for {path}: {e}")
                break
    return populated


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
                # Convert BGR (OpenCV) to RGB (PIL)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                w, h = img.size
                thumb_w = int(w * (max_h / h))
                thumb = img.resize((thumb_w, max_h), Image.Resampling.LANCZOS)
                thumb.save(thumb_path, format="WEBP", quality=82, method=4)
                return True

        # Fallback using ffmpeg if installed
        res = os.system(
            f'ffmpeg -y -ss 00:00:00.500 -i "{video_path}" -vframes 1 -vf "scale=-1:{max_h}" "{thumb_path}" -loglevel quiet'
        )
        return res == 0
    except Exception as e:
        print(f"Error generating video thumbnail: {e}")
        return False


async def process_media_message(
    msg: Any,
    client: TelegramClient,
    existing_ids: Set[str],
    existing_hashes: Set[str],
) -> Optional[Dict[str, Any]]:
    """
    Validates, downloads, checks for duplicates via MD5 hash,
    and generates thumbnail for a Telegram message.
    """
    if not msg.media or not isinstance(msg.media, MessageMediaDocument):
        return None

    item_id = f"tg_{msg.id}"
    if item_id in existing_ids:
        return None

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
            media_type = "video"
            ext = "mp4"
        elif "image" in mime:
            media_type = "image"
            ext = "png" if "png" in mime else "jpg"

    if not media_type or not ext:
        return None

    # In Telegram channels, live wallpapers are posted twice:
    # 1. As an inline video preview (compressed stream video, usually < 1MB)
    # 2. As an uncompressed document (.mp4) with full high resolution (10MB - 30MB)
    # We strictly discard compressed video stream previews (< 1.2MB) to avoid duplicate live wallpapers!
    if media_type == "video" and doc_size < 1_200_000:
        print(f"Skipping low-res video stream preview ({doc_size} bytes): msg_id={msg.id}")
        return None
        return None

    full_filename = f"{item_id}.{ext}"
    thumb_filename = f"{item_id}.webp"
    full_path = os.path.join(FULL_DIR, full_filename)
    thumb_path = os.path.join(THUMB_DIR, thumb_filename)

    print(f"Downloading msg #{msg.id} ({media_type.upper()}: {full_filename})...")
    downloaded = await msg.download_media(file=full_path)
    if not downloaded or not os.path.exists(full_path):
        print(f"Failed to download media for msg #{msg.id}")
        return None

    # Robust deduplication by cryptographic content hash (MD5)
    content_hash = calculate_file_md5(full_path)
    if content_hash in existing_hashes:
        print(f"Duplicate content detected by MD5 hash ({content_hash}). Skipping msg #{msg.id}")
        if os.path.exists(full_path):
            os.remove(full_path)
        return None

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
        return None

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
        "content_hash": content_hash,
    }

    existing_ids.add(item_id)
    existing_hashes.add(content_hash)
    return new_entry


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

    # Populate missing hashes for existing wallpapers if files are present locally
    populated = populate_missing_hashes(catalog)
    if populated > 0:
        print(f"Populated content_hash for {populated} existing wallpapers.")

    existing_wallpapers = catalog.get("wallpapers", [])
    existing_ids: Set[str] = {w["id"] for w in existing_wallpapers}
    existing_hashes: Set[str] = {w.get("content_hash") for w in existing_wallpapers if w.get("content_hash")}

    numeric_ids = [
        int(w["id"][3:])
        for w in existing_wallpapers
        if w.get("id", "").startswith("tg_") and w.get("id", "")[3:].isdigit()
    ]
    min_catalog_id = min(numeric_ids) if numeric_ids else None

    print(f"Catalog loaded: {len(existing_wallpapers)} wallpapers ({len(existing_hashes)} content hashes).")
    if min_catalog_id:
        print(f"Oldest wallpaper in catalog: #tg_{min_catalog_id}")

    print(f"Connecting to Telegram client...")
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
    await client.start()

    print(f"Fetching entity for @{CHANNEL_USERNAME}...")
    entity = await client.get_entity(CHANNEL_USERNAME)

    new_items: List[Dict[str, Any]] = []

    # 1. Recent messages scan (New wallpapers)
    print(f"\n[Fase 1] Varrendo as {RECENT_SCAN_LIMIT} mensagens mais recentes do canal em busca de novidades...")
    async for msg in client.iter_messages(entity, limit=RECENT_SCAN_LIMIT):
        item = await process_media_message(msg, client, existing_ids, existing_hashes)
        if item:
            new_items.append(item)
            print(f" -> [Novo] {item['name']} ({item['type']})")

    # 2. Historical fallback backfill (when no new wallpapers were posted)
    if not new_items and ENABLE_FALLBACK_BACKFILL:
        cursor_id = catalog.get("backfill_cursor_id") or min_catalog_id
        if cursor_id and cursor_id > 1:
            print(f"\n[Fase 2 - Fallback Histórico] Nenhum papel novo encontrado recentemente.")
            print(f"Iniciando busca no histórico do canal anterior à mensagem #{cursor_id}...")
            print(f"Meta: {FALLBACK_BACKFILL_COUNT} papéis antigos (limite de varredura: {HISTORICAL_SCAN_LIMIT} mensagens)")

            oldest_scanned_id = cursor_id
            historical_scanned = 0

            async for msg in client.iter_messages(entity, offset_id=cursor_id, limit=HISTORICAL_SCAN_LIMIT):
                historical_scanned += 1
                oldest_scanned_id = min(oldest_scanned_id, msg.id)

                item = await process_media_message(msg, client, existing_ids, existing_hashes)
                if item:
                    new_items.append(item)
                    print(f" -> [Histórico {len(new_items)}/{FALLBACK_BACKFILL_COUNT}] {item['name']} ({item['type']})")
                    if len(new_items) >= FALLBACK_BACKFILL_COUNT:
                        print(f"Meta de {FALLBACK_BACKFILL_COUNT} wallpapers históricos atingida!")
                        break

            catalog["backfill_cursor_id"] = oldest_scanned_id
            print(f"[Fallback Histórico] Varredura finalizada ({historical_scanned} msgs verificadas).")
            print(f"Cursor histórico atualizado para #{oldest_scanned_id}.")
        else:
            print("\n[Fallback Histórico] Não foi possível determinar cursor histórico ou o canal já foi totalmente minerado.")

    await client.disconnect()

    if not new_items:
        print("\nNenhum papel de parede (recente ou histórico) foi adicionado nesta execução.")
        if populated > 0 or "backfill_cursor_id" in catalog:
            with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
                f.write("\n")
        return

    # Prepend newest items so they show at the top of the app as new arrivals
    catalog["wallpapers"] = new_items + catalog.get("wallpapers", [])

    # Write newly added IDs to temporary file for downstream classifiers
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

    print(f"\nSucesso! {len(new_items)} papéis de parede adicionados ao catálogo.")
    print(f"Tamanho total atual do catálogo: {len(catalog['wallpapers'])} papéis de parede.")


if __name__ == "__main__":
    asyncio.run(main())
