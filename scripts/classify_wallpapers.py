#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unified Wallpaper Classifier supporting:
1. Google Gemini Flash (3.8 / 3.5 / 2.5 / latest with dynamic candidate resolution)
2. Simple AI (Local Computer Vision & MobileNetV3 - runs offline, zero API costs)
3. Both with Fallback (Attempts Gemini first; seamlessly falls back to Simple AI if quota is hit)
"""

import os
import sys
import json
import time
import io
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

# Ensure scripts directory is on sys.path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from classify_with_gemini import (
    analyze_image_with_gemini,
    fetch_image_bytes,
    get_candidate_models,
    STANDARD_CATEGORIES,
    generate_dynamic_notification,
    save_notification,
)

# Optional Torchvision for offline neural vision
try:
    import torch
    import torchvision.transforms as transforms
    from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
    HAS_TORCHVISION = True
except Exception:
    HAS_TORCHVISION = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PROVIDER = os.environ.get("CLASSIFY_PROVIDER", "both_with_fallback").lower().strip()
MAX_PER_RUN = int(os.environ.get("MAX_CLASSIFY_PER_RUN", "50"))
UPGRADE_SIMPLE_AI_RAW = os.environ.get("UPGRADE_SIMPLE_AI", "true").lower().strip()
UPGRADE_SIMPLE_AI = UPGRADE_SIMPLE_AI_RAW in ("true", "1", "yes", "y")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "wallpapers", "catalog.json")
THUMB_DIR = os.path.join(BASE_DIR, "wallpapers", "thumbnails")

KEYWORD_CATEGORY_MAP = {
    "cars": ["car", "automobile", "truck", "motorcycle", "wheel", "racer", "jeep", "cab", "wagon", "convertible", "vehicle", "bus"],
    "nature": ["mountain", "alp", "volcano", "valley", "cliff", "forest", "tree", "flower", "rose", "daisy", "lake", "ocean", "sea", "beach", "coast", "shore", "river", "waterfall", "sunset", "sky", "cloud"],
    "animals": ["dog", "cat", "bird", "lion", "tiger", "bear", "wolf", "fox", "deer", "eagle", "owl", "horse", "fish", "shark", "whale", "butterfly", "insect", "reptile", "snake", "rabbit", "panda"],
    "space": ["space", "shuttle", "rocket", "planet", "star", "astronomy", "telescope", "galaxy"],
    "city": ["building", "skyscraper", "tower", "bridge", "castle", "church", "monastery", "palace", "street", "city"],
    "anime": ["comic", "cartoon", "animation", "drawing", "illustration"],
    "games": ["joystick", "game", "screen", "monitor"],
    "minimal": ["monochrome", "minimal", "texture", "paper"],
    "abstract": ["pattern", "geometric", "spiral", "fractal", "abstract"],
}

_TORCH_MODEL = None
_TORCH_TRANSFORM = None
_IMAGENET_CATEGORIES = None


def extract_dominant_color(img: Image.Image) -> str:
    try:
        small = img.copy().convert("RGB").resize((48, 48), Image.Resampling.BOX)
        palette = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT).getpalette()
        if palette and len(palette) >= 3:
            for i in range(0, min(18, len(palette)), 3):
                r, g, b = palette[i], palette[i + 1], palette[i + 2]
                if (r + g + b) > 40:  # not pitch black
                    return f"#{r:02x}{g:02x}{b:02x}"
            return f"#{palette[0]:02x}{palette[1]:02x}{palette[2]:02x}"
    except Exception:
        pass
    return "#121212"


def is_oled_image(img: Image.Image) -> bool:
    try:
        small = img.copy().convert("L").resize((64, 64), Image.Resampling.BOX)
        if hasattr(small, "get_flattened_data"):
            pixels = list(small.get_flattened_data())
        else:
            pixels = list(small.getdata())
        dark_pixels = sum(1 for p in pixels if p < 15)
        return (dark_pixels / len(pixels)) >= 0.60
    except Exception:
        return False


def get_torch_model():
    global _TORCH_MODEL, _TORCH_TRANSFORM, _IMAGENET_CATEGORIES
    if not HAS_TORCHVISION:
        return None, None, None

    if _TORCH_MODEL is None:
        try:
            weights = MobileNet_V3_Small_Weights.DEFAULT
            _TORCH_MODEL = mobilenet_v3_small(weights=weights)
            _TORCH_MODEL.eval()
            _TORCH_TRANSFORM = weights.transforms()
            _IMAGENET_CATEGORIES = weights.meta["categories"]
            print("[Simple AI] MobileNetV3 neural vision model loaded successfully.")
        except Exception as e:
            print(f"[Simple AI] Notice: Could not load TorchVision weights: {e}")
            return None, None, None

    return _TORCH_MODEL, _TORCH_TRANSFORM, _IMAGENET_CATEGORIES


def analyze_with_simple_ai(image_bytes: bytes, item: Dict[str, Any]) -> Dict[str, Any]:
    """Offline local vision classification using color heuristics and MobileNetV3."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as pil_img:
            pil_rgb = pil_img.convert("RGB")
            color = extract_dominant_color(pil_rgb)
            is_oled = is_oled_image(pil_rgb)
    except Exception as e:
        print(f"[Simple AI] Error processing image bytes: {e}")
        return {}

    is_video = item.get("type") == "video" or item.get("is_live", False)

    if is_video:
        category = "live"
        name = item["name"] if not item["name"].startswith("Wallpaper #") else f"Live Wallpaper #{item['id'].replace('tg_', '')}"
        tags = ["live wallpaper", "video", "motion", "animado", "hd"]
        search_terms = ["live wallpaper", "video", "motion", "animado", "background", "hd", "4k"]
    elif is_oled:
        category = "oled"
        name = item["name"] if not item["name"].startswith("Wallpaper #") else f"OLED Wallpaper #{item['id'].replace('tg_', '')}"
        tags = ["oled", "dark", "preto", "minimalist", "amoled"]
        search_terms = ["oled", "dark", "preto", "minimalist", "amoled", "fundo escuro", "black", "pure black"]
    else:
        detected_category = "abstract"
        detected_labels: List[str] = []

        model, transform, categories = get_torch_model()
        if model is not None and transform is not None and categories is not None:
            try:
                with torch.no_grad():
                    input_tensor = transform(pil_rgb).unsqueeze(0)
                    output = model(input_tensor)
                    probabilities = torch.nn.functional.softmax(output[0], dim=0)
                    top5_prob, top5_catid = torch.topk(probabilities, 5)

                    for i in range(top5_catid.size(0)):
                        cls_name = categories[top5_catid[i]].lower().replace("_", " ")
                        detected_labels.append(cls_name)

                        for cat_id, keywords in KEYWORD_CATEGORY_MAP.items():
                            if any(k in cls_name for k in keywords):
                                detected_category = cat_id
                                break
                        if detected_category != "abstract":
                            break
            except Exception as e:
                print(f"[Simple AI] Inference error: {e}")

        category = detected_category
        clean_item_name = item["name"]

        if clean_item_name.startswith("Wallpaper #") and detected_labels:
            readable_label = detected_labels[0].capitalize()
            name = f"{readable_label} #{item['id'].replace('tg_', '')}"
        else:
            name = clean_item_name

        tags = [category, "wallpaper", "hd", "4k"]
        for lbl in detected_labels[:3]:
            if lbl not in tags:
                tags.append(lbl)

        search_terms = list(dict.fromkeys(tags + [f"{category} background", "mobile wallpaper", "tela de fundo"]))

    return {
        "name": name,
        "category": category,
        "primary_color": color,
        "tags": tags,
        "search_terms": search_terms,
    }


def should_skip_classification(item: Dict[str, Any]) -> bool:
    """Decide whether to classify an item or skip it."""
    # 1. Manual user classifications are strictly preserved
    if item.get("classified_by") == "manual" or item.get("custom_classified") is True:
        return True

    name = item.get("name", "")
    is_generic_name = name.startswith("Wallpaper #") or name.startswith("Live Wallpaper #")
    is_generic_cat = item.get("category", "") in ("images", "unknown", "")

    # Always classify if name or category is generic
    if is_generic_name or is_generic_cat:
        return False

    # Skip if already classified by Gemini and has real name
    if item.get("classified_by") == "gemini":
        return True

    # If classified by Simple AI, skip unless upgrade is enabled
    if item.get("classified_by") == "simple_ai":
        if not UPGRADE_SIMPLE_AI or PROVIDER == "simple_ai":
            return True
        return False

    # If already has rich search terms and not generic
    if not UPGRADE_SIMPLE_AI:
        search_terms = item.get("search_terms")
        if search_terms and len(search_terms) > 3 and len(item.get("tags", [])) > 2:
            return True

    return False


def main():
    if not os.path.exists(CATALOG_PATH):
        print(f"Error: {CATALOG_PATH} not found.")
        sys.exit(1)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    wallpapers = catalog.get("wallpapers", [])
    print(f"=== Viagara Wallpaper Classifier ===")
    print(f"Provider: {PROVIDER}")
    print(f"Batch limit: {MAX_PER_RUN}")
    print(f"Upgrade generic/simple AI: {UPGRADE_SIMPLE_AI}")
    print(f"Total wallpapers in catalog: {len(wallpapers)}")

    categories_dict = {c["id"]: c for c in STANDARD_CATEGORIES}
    existing_cat_ids = set(categories_dict.keys())

    # Prioritize newly backfilled items if available
    new_ids_file = os.path.join(BASE_DIR, "wallpapers", ".newly_added_ids.json")
    priority_ids = set()
    if os.path.exists(new_ids_file):
        try:
            with open(new_ids_file, "r", encoding="utf-8") as f:
                priority_ids = set(json.load(f))
            os.remove(new_ids_file)
            print(f"Prioritizing {len(priority_ids)} newly backfilled wallpapers.")
        except Exception:
            pass

    # Filter candidates with strict priority:
    # 0: Explicit new IDs (.newly_added_ids.json)
    # 1: Brand new / unclassified / generic name wallpapers
    # 2: Existing Simple AI wallpapers to be upgraded by Gemini
    candidates = [w for w in wallpapers if not should_skip_classification(w)]

    def get_candidate_priority(item: Dict[str, Any]) -> int:
        if item.get("id") in priority_ids:
            return 0
        name = item.get("name", "")
        cat = item.get("category", "")
        cb = item.get("classified_by")
        if cb is None or cb == "" or name.startswith("Wallpaper #") or name.startswith("Live Wallpaper #") or cat in ("images", "unknown", ""):
            return 1
        if cb == "simple_ai":
            return 2
        return 3

    to_classify = sorted(candidates, key=get_candidate_priority)
    print(f"Wallpapers needing classification: {len(to_classify)}")

    if not to_classify:
        print("All wallpapers are already classified. Nothing to do!")
        return

    active_provider = PROVIDER
    updated_count = 0
    updated_items: List[Dict[str, Any]] = []
    gemini_fail_count = 0

    for idx, item in enumerate(to_classify[:MAX_PER_RUN]):
        item_id = item["id"]
        image_bytes = fetch_image_bytes(item)
        if not image_bytes:
            print(f" -> Skipping {item_id}: could not load image bytes.")
            continue

        result = None
        used_method = ""

        # Attempt Gemini Flash
        if active_provider in ("gemini", "both_with_fallback"):
            if GEMINI_API_KEY:
                print(f"[{idx+1}/{min(len(to_classify), MAX_PER_RUN)}] Classifying {item_id} with Gemini Flash...")
                result = analyze_image_with_gemini(image_bytes, GEMINI_API_KEY)
                if result:
                    used_method = "gemini"
                    gemini_fail_count = 0
                else:
                    gemini_fail_count += 1
                    print(f" -> Gemini returned no response (fails: {gemini_fail_count}).")
                    if active_provider == "both_with_fallback" and gemini_fail_count >= 3:
                        print("\n[Notice] Switching to Simple AI (Local Vision) fallback for remaining items...")
                        active_provider = "simple_ai"

        # Fallback or direct Simple AI
        if not result and (active_provider == "simple_ai" or active_provider == "both_with_fallback"):
            print(f"[{idx+1}/{min(len(to_classify), MAX_PER_RUN)}] Classifying {item_id} with Simple AI (Local Vision)...")
            result = analyze_with_simple_ai(image_bytes, item)
            if result:
                used_method = "simple_ai"

        if result:
            name = result.get("name", item["name"]).strip()
            cat = result.get("category", "abstract").lower().strip()
            color = result.get("primary_color", item.get("primary_color", "#121212"))
            search_terms = result.get("search_terms", item.get("tags", []))
            tags = result.get("tags", search_terms[:5])

            is_video = item.get("type") == "video" or item.get("is_live", False)
            assigned_cat = "live" if is_video else cat

            item["name"] = name
            item["category"] = assigned_cat
            item["primary_color"] = color
            item["search_terms"] = search_terms
            item["tags"] = list(dict.fromkeys(tags))
            item["classified_by"] = used_method

            if assigned_cat not in existing_cat_ids:
                label = assigned_cat.replace("_", " ").capitalize()
                categories_dict[assigned_cat] = {"id": assigned_cat, "label": label}
                existing_cat_ids.add(assigned_cat)

            updated_count += 1
            updated_items.append(item)
            print(f" -> [{used_method.upper()}] '{name}' | Categoria: {assigned_cat} | Cor: {color} | Tags: {', '.join(item['tags'][:4])}")

            # Progressive save
            catalog["categories"] = list(categories_dict.values())
            catalog["wallpapers"] = wallpapers
            with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
                f.write("\n")

            if used_method == "gemini":
                time.sleep(3.5)
            else:
                time.sleep(0.1)

    catalog["categories"] = list(categories_dict.values())
    catalog["wallpapers"] = wallpapers
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if updated_items:
        print(f"\n[Notification] Gerando notificação dinâmica para {len(updated_items)} papéis de parede...")
        notif = generate_dynamic_notification(updated_items, GEMINI_API_KEY)
        save_notification(notif, catalog)

    print(f"\nDone! Successfully classified {updated_count} wallpapers.")


if __name__ == "__main__":
    main()
