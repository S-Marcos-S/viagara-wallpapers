#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Process wallpapers submitted via GitHub Issues:
- Extracts image/video URLs (supports GitHub user-attachments and direct links).
- Downloads each file in full resolution (100% bit-for-bit fidelity).
- Generates high-quality WebP thumbnail preserving aspect ratio.
- Updates catalog.json with deduplication check (MD5 hash).
- Prepares items for Gemini AI classification.
- Generates markdown summary for the Issue comment.
"""

import os
import sys
import json
import re
import io
import ssl
import hashlib
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Tuple

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import requests
except ImportError:
    requests = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALLPAPERS_DIR = os.path.join(BASE_DIR, "wallpapers")
FULL_DIR = os.path.join(WALLPAPERS_DIR, "full")
THUMB_DIR = os.path.join(WALLPAPERS_DIR, "thumbnails")
CATALOG_PATH = os.path.join(WALLPAPERS_DIR, "catalog.json")
SUMMARY_PATH = os.path.join(BASE_DIR, "issue_summary.md")

RAW_BASE_URL = "https://raw.githubusercontent.com/S-Marcos-S/viagara-wallpapers/main/wallpapers"

os.makedirs(FULL_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)


def calculate_md5(data: bytes) -> str:
    """Calculate MD5 hash of raw bytes."""
    return hashlib.md5(data).hexdigest()


def extract_urls_from_text(text: str) -> List[str]:
    """Extract all candidate image/video URLs from issue markdown body."""
    patterns = [
        # Modern GitHub user attachments: https://github.com/user-attachments/assets/<uuid>
        r"https://github\.com/user-attachments/assets/[a-zA-Z0-9_\-]+",
        # Legacy repo assets: https://github.com/<owner>/<repo>/assets/<user_id>/<uuid>
        r"https://github\.com/[^/\s]+/[^/\s]+/assets/[0-9]+/[a-zA-Z0-9_\-]+",
        # GitHub files: https://github.com/<owner>/<repo>/files/<id>/<filename>
        r"https://github\.com/[^/\s]+/[^/\s]+/files/[0-9]+/[^\s\)\"\'>]+",
        # Direct image/video links (PNG, JPG, WEBP, MP4)
        r"https?://[^\s\)\"\'<>]+?\.(?:png|jpg|jpeg|webp|mp4)(?:\?[^\s\)\"\'<>]*)?",
    ]

    urls: List[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            cleaned = m.strip()
            # Discard internal URLs pointing to existing repo wallpapers/thumbnails
            if "viagara-wallpapers/main/wallpapers" in cleaned or "wallpapers-foss/main/wallpapers" in cleaned:
                continue
            if cleaned and cleaned not in urls:
                urls.append(cleaned)

    return urls


def extract_custom_author_and_title(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Check if the user specified Author or Title in the text."""
    author = None
    title = None

    author_match = re.search(r"(?:autor|author|créditos|credits)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
    if author_match:
        author = author_match.group(1).strip()

    title_match = re.search(r"(?:título|titulo|title)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()

    return author, title


def download_asset(url: str, token: str = "") -> Optional[bytes]:
    """Downloads binary asset with user-agent, cleanly following redirects."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    # 1. Try requests if available (best handling of cross-domain auth stripping on S3 redirects)
    if requests is not None:
        try:
            req_headers = dict(headers)
            if token and "github.com" in url:
                req_headers["Authorization"] = f"token {token}"
            resp = requests.get(url, headers=req_headers, stream=True, timeout=60, allow_redirects=True)
            if resp.status_code == 200:
                return resp.content
            print(f"[Downloader] requests HTTP {resp.status_code} for {url}")
        except Exception as e:
            print(f"[Downloader] requests exception for {url}: {e}")

    # 2. Fallback to urllib.request
    try:
        req = urllib.request.Request(url, headers=headers)
        if token and "github.com" in url:
            req.add_header("Authorization", f"token {token}")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            return response.read()
    except Exception as e:
        print(f"[Downloader] urllib exception for {url}: {e}")
        return None


def detect_media_type_and_ext(data: bytes, url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Determines media type ('image' or 'video') and standard extension ('jpg', 'png', 'webp', 'mp4').
    """
    # Check MP4 video signature (ftyp starting at byte offset 4)
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video", "mp4"

    # Check images via PIL
    if HAS_PIL:
        try:
            with Image.open(io.BytesIO(data)) as img:
                fmt = (img.format or "").upper()
                if fmt in ("JPEG", "JPG"):
                    return "image", "jpg"
                elif fmt == "PNG":
                    return "image", "png"
                elif fmt == "WEBP":
                    return "image", "webp"
                elif fmt in ("GIF", "BMP", "TIFF"):
                    return "image", "jpg"
        except Exception:
            pass

    # Fallback to URL extension
    clean_url = url.split("?")[0].lower()
    if clean_url.endswith((".jpg", ".jpeg")):
        return "image", "jpg"
    elif clean_url.endswith(".png"):
        return "image", "png"
    elif clean_url.endswith(".webp"):
        return "image", "webp"
    elif clean_url.endswith(".mp4"):
        return "video", "mp4"

    return None, None


def save_full_image(data: bytes, ext: str, target_path: str) -> Tuple[bool, int, int]:
    """
    Saves full image with 100% resolution fidelity.
    If EXIF orientation requires rotation, applies it losslessly/max quality.
    Otherwise dumps raw binary bytes directly.
    Returns (success, width, height).
    """
    if not HAS_PIL:
        with open(target_path, "wb") as f:
            f.write(data)
        return True, 0, 0

    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            exif = img.getexif()
            orientation = exif.get(0x0112)

            # Check if camera orientation rotation is needed
            if orientation and orientation > 1:
                transposed = ImageOps.exif_transpose(img)
                tw, th = transposed.size
                if ext == "jpg":
                    transposed.convert("RGB").save(target_path, format="JPEG", quality=100, subsampling=0)
                elif ext == "png":
                    transposed.save(target_path, format="PNG")
                elif ext == "webp":
                    transposed.save(target_path, format="WEBP", lossless=True)
                else:
                    transposed.convert("RGB").save(target_path, format="JPEG", quality=100)
                return True, tw, th
            else:
                # Direct raw byte dump: zero re-encoding, pure original quality!
                with open(target_path, "wb") as f:
                    f.write(data)
                return True, w, h
    except Exception as e:
        print(f"Error saving full image {target_path}: {e}")
        return False, 0, 0


def generate_image_thumbnail(full_path: str, thumb_path: str, target_short: int = 720, max_long: int = 1600) -> bool:
    """
    Generates high-resolution WebP thumbnail preserving aspect ratio.
    Target short side: 720px (ensures crisp display on FHD+ and QHD+ displays with ContentScale.Crop).
    """
    if not HAS_PIL:
        return False

    try:
        with Image.open(full_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            w, h = img.size

            short_side = min(w, h)
            if short_side <= 0:
                return False

            scale = target_short / float(short_side)
            if max(w, h) * scale > max_long:
                scale = max_long / float(max(w, h))

            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))

            thumb = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            thumb.save(thumb_path, format="WEBP", quality=84, method=4)
            return True
    except Exception as e:
        print(f"Error generating image thumbnail: {e}")
        return False


def generate_video_thumbnail(video_path: str, thumb_path: str, target_short: int = 720) -> bool:
    """Extracts first high-quality frame from MP4 video for thumbnail."""
    try:
        if cv2 is not None:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            # Seek 0.5s to avoid black frames
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 0.5))
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
            cap.release()

            if success and HAS_PIL:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                w, h = img.size
                scale = target_short / float(min(w, h))
                thumb = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
                thumb.save(thumb_path, format="WEBP", quality=84, method=4)
                return True

        # Fallback using ffmpeg
        res = os.system(
            f'ffmpeg -y -ss 00:00:00.500 -i "{video_path}" -vframes 1 -vf "scale=\'if(gt(a,1),-1,{target_short})\':\'if(gt(a,1),{target_short},-1)\'" "{thumb_path}" -loglevel quiet'
        )
        return res == 0
    except Exception as e:
        print(f"Error generating video thumbnail: {e}")
        return False


def main():
    issue_number = os.environ.get("ISSUE_NUMBER", "").strip()
    issue_author = os.environ.get("ISSUE_AUTHOR", "").strip()
    issue_author_url = os.environ.get("ISSUE_AUTHOR_URL", "").strip()
    gh_token = os.environ.get("GH_TOKEN", "").strip()

    # Read issue data from file if provided (generated by gh api)
    issue_data_file = os.environ.get("ISSUE_DATA_FILE", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_title = ""

    if issue_data_file and os.path.exists(issue_data_file):
        try:
            with open(issue_data_file, "r", encoding="utf-8") as f:
                issue_json = json.load(f)
                issue_body = issue_json.get("body", "") or ""
                issue_title = issue_json.get("title", "") or ""
                if not issue_number:
                    issue_number = str(issue_json.get("number", ""))
                user_obj = issue_json.get("user", {})
                if not issue_author:
                    issue_author = user_obj.get("login", "")
                if not issue_author_url:
                    issue_author_url = user_obj.get("html_url", f"https://github.com/{issue_author}")
        except Exception as e:
            print(f"Warning reading {issue_data_file}: {e}")

    # Check if this issue is actually a wallpaper suggestion, not an upload
    if (
        "[Sugestão]" in issue_title
        or "[sugestão]" in issue_title.lower()
        or "custom_classified" in issue_body
        or "Sugestão de Classificação Manual" in issue_body
    ):
        print("Notice: Issue is a wallpaper edit suggestion, not a new upload. Exiting gracefully.")
        set_github_output("new_count", "0")
        set_github_output("has_new_wallpapers", "false")
        sys.exit(0)

    if not issue_number:
        issue_number = "manual"

    if not issue_author:
        issue_author = "Comunidade"
    if not issue_author_url:
        issue_author_url = f"https://github.com/{issue_author}" if issue_author != "Comunidade" else ""

    custom_author, custom_title = extract_custom_author_and_title(issue_body)
    effective_author = custom_author if custom_author else issue_author

    print(f"=== Process Issue Wallpapers ===")
    print(f"Issue: #{issue_number} by @{issue_author}")
    print(f"Effective Author: {effective_author}")

    urls = extract_urls_from_text(issue_body)
    print(f"Found {len(urls)} candidate URLs in issue body.")

    if not urls:
        print("No image or video URLs found in issue body.")
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            f.write("⚠️ **Nenhuma imagem válida foi encontrada** na descrição desta Issue.\n\nCertifique-se de anexar as fotos da galeria diretamente no corpo da mensagem.")
        set_github_output("new_count", "0")
        set_github_output("has_new_wallpapers", "false")
        sys.exit(0)

    # Load existing catalog
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    else:
        catalog = {"version": 1, "categories": [], "wallpapers": []}

    existing_wallpapers = catalog.get("wallpapers", [])
    existing_ids = {w["id"] for w in existing_wallpapers}
    existing_hashes = {w.get("content_hash") for w in existing_wallpapers if w.get("content_hash")}

    added_items: List[Dict[str, Any]] = []
    skipped_duplicates: List[str] = []

    for idx, url in enumerate(urls, start=1):
        print(f"\n[{idx}/{len(urls)}] Processing URL: {url} ...")
        data = download_asset(url, token=gh_token)
        if not data:
            print(f" -> Failed to download data from {url}")
            continue

        media_type, ext = detect_media_type_and_ext(data, url)
        if not media_type or not ext:
            print(f" -> Unsupported media type for URL: {url}")
            continue

        content_hash = calculate_md5(data)
        if content_hash in existing_hashes:
            print(f" -> Duplicate content detected (MD5: {content_hash}). Skipping.")
            skipped_duplicates.append(url)
            continue

        # Generate unique identifier
        item_id = f"wp_i{issue_number}_{idx}"
        counter = 1
        while item_id in existing_ids:
            item_id = f"wp_i{issue_number}_{idx}_{counter}"
            counter += 1

        full_filename = f"{item_id}.{ext}"
        thumb_filename = f"{item_id}.webp"
        full_path = os.path.join(FULL_DIR, full_filename)
        thumb_path = os.path.join(THUMB_DIR, thumb_filename)

        is_video = (media_type == "video")
        width, height = 0, 0

        if is_video:
            with open(full_path, "wb") as f:
                f.write(data)
            thumb_ok = generate_video_thumbnail(full_path, thumb_path)
        else:
            save_ok, width, height = save_full_image(data, ext, full_path)
            if not save_ok:
                print(f" -> Failed to save full image for {item_id}")
                continue
            thumb_ok = generate_image_thumbnail(full_path, thumb_path)

        if not thumb_ok:
            print(f" -> Failed to generate thumbnail for {item_id}")
            if os.path.exists(full_path):
                os.remove(full_path)
            continue

        item_title = custom_title if (custom_title and len(urls) == 1) else f"Wallpaper #{item_id}"

        new_entry = {
            "id": item_id,
            "name": item_title,
            "author": effective_author,
            "author_url": issue_author_url,
            "thumbnail_url": f"{RAW_BASE_URL}/thumbnails/{thumb_filename}",
            "full_url": f"{RAW_BASE_URL}/full/{full_filename}",
            "primary_color": "#121212",
            "category": "live" if is_video else "images",
            "type": media_type,
            "is_live": is_video,
            "tags": ["live", "video"] if is_video else ["image", "hd", "4k"],
            "search_terms": [],
            "content_hash": content_hash,
            "classified_by": None,
            "resolution": f"{width}x{height}" if width and height else None,
        }

        # Add to front of catalog
        existing_wallpapers.insert(0, new_entry)
        existing_ids.add(item_id)
        existing_hashes.add(content_hash)
        added_items.append(new_entry)

        print(f" -> Successfully registered {item_id} ({media_type.upper()}, {width}x{height})")

    # Save catalog
    catalog["wallpapers"] = existing_wallpapers
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nRegistered {len(added_items)} new wallpapers in catalog.json.")
    print(f"Skipped duplicates: {len(skipped_duplicates)}")

    # Build Markdown Summary for Issue comment
    summary_lines = []
    if added_items:
        summary_lines.append(f"## 🎉 {len(added_items)} Novos Papéis de Parede Adicionados!")
        summary_lines.append("")
        summary_lines.append("As imagens foram integradas ao repositório em **resolução original máxima** (100% de fidelidade) e já estão prontas para exibição no **Wallpapers FOSS**.")
        summary_lines.append("")
        summary_lines.append("| Miniatura | ID | Tipo | Resolução Original | Créditos |")
        summary_lines.append("| :---: | :---: | :---: | :---: | :---: |")

        for it in added_items:
            res_str = it.get("resolution") or "Original"
            tipo_str = "🎥 Live Video" if it["is_live"] else "🖼️ Imagem Estática"
            author_link = f"[{it['author']}]({it['author_url']})" if it.get("author_url") else it["author"]
            summary_lines.append(
                f"| <img src=\"{it['thumbnail_url']}\" width=\"90\" /> | `{it['id']}` | {tipo_str} | `{res_str}` | {author_link} |"
            )

        summary_lines.append("")
        summary_lines.append("✨ **Google Gemini AI:** O classificador inteligente categorizou o conteúdo com tags de busca e cores predominantes.")
        summary_lines.append("📱 **Sincronização:** Disponível imediatamente na aba de papéis de parede do launcher.")
    else:
        summary_lines.append("⚠️ **Nenhum novo papel de parede adicionado.**")
        if skipped_duplicates:
            summary_lines.append(f"\nTodas as {len(skipped_duplicates)} imagem(ns) enviada(s) já existem no catálogo oficial (duplicata detectada via hash MD5).")

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    set_github_output("new_count", str(len(added_items)))
    set_github_output("has_new_wallpapers", "true" if added_items else "false")


def set_github_output(name: str, value: str):
    """Write output variable for GitHub Actions step."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file and os.path.exists(output_file):
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"[Output] {name}={value}")


if __name__ == "__main__":
    main()
