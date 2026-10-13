#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unified Wallpaper Classifier supporting:
1. Google Gemini Flash (Generative semantic AI for rich tags and character names)
2. Simple AI (Local Computer Vision & MobileNetV3 - runs offline, zero API costs, zero rate limits)
3. Both with Fallback (Attempts Gemini first; seamlessly falls back to Simple AI if quota/429 is hit)
"""

import os
import sys
import json
import base64
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "wallpapers", "catalog.json")
THUMB_DIR = os.path.join(BASE_DIR, "wallpapers", "thumbnails")

STANDARD_CATEGORIES = [
    {"id": "all", "label": "Todos"},
    {"id": "live", "label": "Live Wallpapers"},
    {"id": "anime", "label": "Anime"},
    {"id": "games", "label": "Jogos"},
    {"id": "nature", "label": "Natureza"},
    {"id": "space", "label": "Espaço"},
    {"id": "cars", "label": "Carros"},
    {"id": "city", "label": "Cidades"},
    {"id": "animals", "label": "Animais"},
    {"id": "oled", "label": "OLED"},
    {"id": "minimal", "label": "Minimalista"},
    {"id": "abstract", "label": "Abstrato"},
    {"id": "cyberpunk", "label": "Cyberpunk"},
    {"id": "fantasy", "label": "Fantasia"},
]

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

GEMINI_PROMPT = """Você é um especialista em classificação e catalogação visual de papéis de parede mobile para um aplicativo Android.
Analise detalhadamente a imagem fornecida e retorne APENAS um JSON válido no seguinte formato:

{
  "name": "Nome descritivo preciso (ex: Naruto Uzumaki, Pôr do Sol na Praia, Cyberpunk City, McLaren 720S, Goku Super Saiyajin)",
  "category": "Uma das opções: anime, games, nature, space, cars, city, animals, oled, minimal, abstract, cyberpunk, fantasy (ou crie uma categoria curta em minúsculas se realmente não se encaixar em nenhuma)",
  "primary_color": "#HEX (cor dominante da imagem)",
  "search_terms": [
    "lista de 6 a 12 palavras-chave e termos de pesquisa em português e inglês detalhando os elementos visuais exatos que aparecem na imagem, personagens, cores, objetos, ambiente, etc."
  ]
}

Regras:
1. Se a imagem contiver um personagem famoso de anime, mangá, quadrinho ou jogo, identifique o personagem pelo nome exato no campo "name" e adicione o anime/jogo nos search_terms.
2. Seja detalhista nos search_terms (ex para montanha: "montanha", "céu azul", "neve", "pico", "nuvens", "natureza", "mountain", "blue sky").
3. Responda SOMENTE o bloco JSON puro, sem markdown ```json``` ou texto explicativo antes/depois.
"""

_ACTIVE_FLASH_MODEL = None
_TORCH_MODEL = None
_TORCH_TRANSFORM = None
_IMAGENET_CATEGORIES = None


def get_active_flash_model(api_key: str) -> str:
    global _ACTIVE_FLASH_MODEL
    if _ACTIVE_FLASH_MODEL:
        return _ACTIVE_FLASH_MODEL

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "ViagaraClassifier/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        available = [
            m["name"].replace("models/", "")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]

        preferred = [
            "gemini-3.8-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
        ]
        for pref in preferred:
            if pref in available:
                _ACTIVE_FLASH_MODEL = pref
                print(f"[Gemini] Selected active model: {_ACTIVE_FLASH_MODEL}")
                return _ACTIVE_FLASH_MODEL

        flash_candidates = [
            m for m in available
            if "flash" in m.lower()
            and "omni" not in m.lower()
            and "audio" not in m.lower()
            and "live" not in m.lower()
            and "preview" not in m.lower()
        ]
        if flash_candidates:
            _ACTIVE_FLASH_MODEL = flash_candidates[0]
            print(f"[Gemini] Selected candidate model: {_ACTIVE_FLASH_MODEL}")
            return _ACTIVE_FLASH_MODEL
    except Exception as e:
        print(f"[Gemini] Dynamic model check warning: {e}")

    _ACTIVE_FLASH_MODEL = "gemini-3.8-flash"
    return _ACTIVE_FLASH_MODEL


def analyze_with_gemini(image_path: str, api_key: str, max_retries: int = 2) -> Optional[Dict[str, Any]]:
    if not os.path.exists(image_path) or not api_key:
        return None

    try:
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"Error reading {image_path}: {e}")
        return None

    model_name = get_active_flash_model(api_key)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": GEMINI_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/webp",
                            "data": b64_img,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"[Gemini] Rate limit 429 on attempt {attempt+1}.")
                time.sleep(8)
            else:
                return None
        except Exception as e:
            print(f"[Gemini] API error: {e}")
            time.sleep(2)

    return None


def extract_dominant_color(img: Image.Image) -> str:
    try:
        small = img.copy().convert("RGB").resize((48, 48), Image.Resampling.BOX)
        palette = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT).getpalette()
        if palette and len(palette) >= 3:
            # Pick the most vibrant non-black color or default to first
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
        gray = img.copy().convert("L").resize((64, 64))
        pixels = list(gray.getdata())
        dark_pixels = sum(1 for p in pixels if p < 25)
        return (dark_pixels / len(pixels)) >= 0.55
    except Exception:
        return False


def get_torch_model():
    global _TORCH_MODEL, _TORCH_TRANSFORM, _IMAGENET_CATEGORIES
    if not HAS_TORCHVISION:
        return None, None, None

    if _TORCH_MODEL is None:
        try:
            weights = MobileNet_V3_Small_Weights.DEFAULT
            _TORCH_MODEL = mobilenet_v3_small(weights=weights).eval()
            _TORCH_TRANSFORM = weights.transforms()
            _IMAGENET_CATEGORIES = weights.meta["categories"]
            print("[Simple AI] MobileNetV3 neural vision model loaded successfully.")
        except Exception as e:
            print(f"[Simple AI] Notice: Could not load TorchVision weights: {e}")
            return None, None, None

    return _TORCH_MODEL, _TORCH_TRANSFORM, _IMAGENET_CATEGORIES


def analyze_with_simple_ai(image_path: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Offline local vision classification using:
    - Dominant color extraction & OLED dark thresholding
    - MobileNetV3 top-class detection (if torchvision available)
    - Visual heuristic color & pattern mapping
    """
    if not os.path.exists(image_path):
        return {}

    with Image.open(image_path) as pil_img:
        pil_rgb = pil_img.convert("RGB")
        color = extract_dominant_color(pil_rgb)
        is_oled = is_oled_image(pil_rgb)

    is_video = item.get("type") == "video" or item.get("is_live", False)

    # 1. Base category determination
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

                        # Match class against known category keyword lists
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

        # Generate descriptive name if still generic
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
        "tags": tags[:5],
        "search_terms": search_terms[:10],
    }


def should_skip_classification(item: Dict[str, Any]) -> bool:
    if item.get("classified_by") in ("manual", "gemini"):
        return True
    if item.get("custom_classified") is True:
        return True
    search_terms = item.get("search_terms")
    if search_terms and len(search_terms) > 3:
        return True
    name = item.get("name", "")
    is_generic = name.startswith("Wallpaper #") or name.startswith("Live Wallpaper #")
    if not is_generic and len(item.get("tags", [])) > 2:
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
            print(f"Prioritizing {len(priority_ids)} newly backfilled wallpapers for classification.")
        except Exception:
            pass

    # Filter candidates
    candidates = [w for w in wallpapers if not should_skip_classification(w)]
    to_classify = sorted(candidates, key=lambda w: 0 if w.get("id") in priority_ids else 1)
    print(f"Wallpapers needing classification: {len(to_classify)}")

    if not to_classify:
        print("All wallpapers are already classified. Nothing to do!")
        return

    active_provider = PROVIDER
    updated_count = 0
    gemini_fail_count = 0

    for idx, item in enumerate(to_classify[:MAX_PER_RUN]):
        item_id = item["id"]
        thumb_path = os.path.join(THUMB_DIR, f"{item_id}.webp")
        if not os.path.exists(thumb_path):
            continue

        result = None
        used_method = ""

        # Attempt Gemini Flash
        if active_provider in ("gemini", "both_with_fallback"):
            if GEMINI_API_KEY:
                print(f"[{idx+1}/{min(len(to_classify), MAX_PER_RUN)}] Classifying {item_id} with Gemini Flash...")
                result = analyze_with_gemini(thumb_path, GEMINI_API_KEY)
                if result:
                    used_method = "gemini"
                    gemini_fail_count = 0
                else:
                    gemini_fail_count += 1
                    print(f" -> Gemini returned no response or quota reached (fails: {gemini_fail_count}).")
                    if active_provider == "both_with_fallback" and gemini_fail_count >= 2:
                        print("\n[Notice] Switching to Simple AI (Local Vision) fallback for remaining items...")
                        active_provider = "simple_ai"

        # Fallback or direct Simple AI
        if not result and (active_provider == "simple_ai" or active_provider == "both_with_fallback"):
            print(f"[{idx+1}/{min(len(to_classify), MAX_PER_RUN)}] Classifying {item_id} with Simple AI (Local Vision)...")
            result = analyze_with_simple_ai(thumb_path, item)
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
            print(f" -> [{used_method.upper()}] '{name}' | Categoria: {assigned_cat} | Cor: {color} | Tags: {', '.join(item['tags'][:4])}")

            # Save progress progressively
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

    print(f"\nDone! Successfully classified {updated_count} wallpapers.")


if __name__ == "__main__":
    main()
