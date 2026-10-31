#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
AI Wallpaper Classifier using Google Gemini Flash (3.8 / 3.5 / 2.5 / latest).
Analyzes wallpaper thumbnails to determine:
- Accurate character/scene/subject title
- Semantic category (anime, games, nature, space, cars, city, animals, oled, minimal, abstract, cyberpunk, fantasy)
- Rich search terms and tags in Portuguese & English for instant search in the launcher
- Primary dominant color hex
"""

import os
import sys
import json
import base64
import time
import io
import re
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
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

PREFERRED_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-flash-latest",
]

PROMPT = """Você é um especialista em classificação e catalogação visual de papéis de parede mobile para um aplicativo Android (Viagara Launcher).
Analise detalhadamente a imagem fornecida e retorne APENAS um JSON válido no seguinte formato:

{
  "name": "Nome descritivo preciso do que aparece na imagem (ex: 'Goku Super Saiyajin', 'Porsche 911 GT3 RS', 'Pôr do Sol na Praia', 'Cyberpunk Neon City', 'Nebulosa de Órion')",
  "category": "Uma das opções exatas: anime, games, nature, space, cars, city, animals, oled, minimal, abstract, cyberpunk, fantasy",
  "primary_color": "#HEX (cor dominante e marcante da imagem)",
  "tags": [
    "5 a 8 tags principais curtas e relevantes em inglês e português, ex: anime, goku, dragon ball, dark, 4k"
  ],
  "search_terms": [
    "8 a 15 palavras-chave e termos de pesquisa em português e inglês detalhando os elementos visuais exatos que aparecem na imagem, personagens, cores, objetos, ambiente, etc."
  ]
}

Regras obrigatórias:
1. Se a imagem contiver um personagem famoso de anime, mangá, quadrinho, filme ou jogo, identifique o personagem pelo nome exato no campo 'name' e adicione o anime/jogo nos search_terms e tags.
2. Se a imagem for predominantemente preta ou escura com alto contraste (ótima para telas AMOLED), inclua 'oled' e 'dark' nas tags e defina a categoria como 'oled' se não for anime/games/cars.
3. Seja detalhista nos search_terms para busca no launcher (ex: montanha, céu azul, neve, pico, nuvens, natureza, mountain, blue sky, clouds).
4. Responda SOMENTE o bloco JSON puro, sem formatação markdown ```json ou texto explicativo antes/depois.
"""

_ACTIVE_MODEL_INDEX = 0
_CANDIDATE_MODELS: Optional[List[str]] = None


def get_candidate_models(api_key: str) -> List[str]:
    """Query official Google AI Studio models endpoint to pick the active Flash models in priority order."""
    global _CANDIDATE_MODELS
    if _CANDIDATE_MODELS is not None:
        return _CANDIDATE_MODELS

    candidates: List[str] = []
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "ViagaraClassifier/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        available = [
            m["name"].replace("models/", "")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]

        # Prioritize according to our preferred models list
        for pref in PREFERRED_MODELS:
            if pref in available:
                candidates.append(pref)

        # Append any other flash models found
        for m in available:
            m_lower = m.lower()
            if "flash" in m_lower and "omni" not in m_lower and "audio" not in m_lower and "live" not in m_lower and m not in candidates:
                candidates.append(m)

        if candidates:
            print(f"[Gemini] Candidate models discovered from API: {', '.join(candidates)}")
            _CANDIDATE_MODELS = candidates
            return _CANDIDATE_MODELS
    except Exception as e:
        print(f"[Gemini] Notice: Could not list models dynamically: {e}")

    # Fallback to preferred models list
    _CANDIDATE_MODELS = list(PREFERRED_MODELS)
    return _CANDIDATE_MODELS


def prepare_image(image_bytes: bytes, max_dim: int = 512) -> Tuple[str, str]:
    """
    Optimizes thumbnail size to max 512px to minimize visual token consumption (only ~258 tokens per call).
    Returns (base64_encoded_str, mime_type).
    """
    if HAS_PIL:
        try:
            bio = io.BytesIO(image_bytes)
            with Image.open(bio) as img:
                img = img.convert("RGB")
                w, h = img.size
                if max(w, h) > max_dim:
                    scale = max_dim / float(max(w, h))
                    new_w = max(1, int(w * scale))
                    new_h = max(1, int(h * scale))
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                out_io = io.BytesIO()
                img.save(out_io, format="JPEG", quality=85)
                return base64.b64encode(out_io.getvalue()).decode("utf-8"), "image/jpeg"
        except Exception as e:
            print(f"[Image] Resize fallback: {e}")

    # Fallback if PIL fails or isn't available
    return base64.b64encode(image_bytes).decode("utf-8"), "image/webp"


def clean_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Clean markdown code fences and extract valid JSON."""
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    try:
        return json.loads(clean)
    except Exception:
        # Regex search for first outer {...}
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def fetch_image_bytes(item: Dict[str, Any]) -> Optional[bytes]:
    """Retrieve image bytes either from local disk or by downloading the thumbnail URL."""
    item_id = item["id"]

    # 1. Check local thumbnail
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        local_path = os.path.join(THUMB_DIR, f"{item_id}{ext}")
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception:
                pass

    # 2. Download from thumbnail_url or full_url
    url = item.get("thumbnail_url") or item.get("full_url")
    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ViagaraClassifier/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception as e:
            print(f"[Image] Failed to download {url}: {e}")

    return None


def analyze_image_with_gemini(image_bytes: bytes, api_key: str, max_retries: int = 2) -> Optional[Dict[str, Any]]:
    """Call Google Gemini Flash with automatic model fallback and rate limiting backoff."""
    global _ACTIVE_MODEL_INDEX
    candidates = get_candidate_models(api_key)

    b64_img, mime_type = prepare_image(image_bytes)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
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

    # Attempt with current active model, falling back through candidates on 404/400
    while _ACTIVE_MODEL_INDEX < len(candidates):
        model_name = candidates[_ACTIVE_MODEL_INDEX]
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

                candidates_list = resp_data.get("candidates", [])
                if not candidates_list:
                    return None

                parts = candidates_list[0].get("content", {}).get("parts", [])
                if not parts:
                    return None

                raw_text = parts[0].get("text", "")
                result = clean_json_response(raw_text)
                if result:
                    return result
            except urllib.error.HTTPError as e:
                # If model is not found or unsupported, rotate to next candidate
                if e.code in (404, 400):
                    print(f"[Gemini] Model '{model_name}' returned HTTP {e.code}. Trying next candidate...")
                    _ACTIVE_MODEL_INDEX += 1
                    break  # Break inner retry loop to try next model
                elif e.code == 429:
                    wait_sec = 8 * (attempt + 1)
                    print(f"[Gemini] Rate limit 429 on '{model_name}'. Waiting {wait_sec}s before retry...")
                    time.sleep(wait_sec)
                else:
                    err_msg = e.read().decode("utf-8", errors="ignore")
                    print(f"[Gemini] HTTP {e.code} ({model_name}): {err_msg[:120]}")
                    time.sleep(2)
            except Exception as e:
                print(f"[Gemini] Request error ({model_name}): {e}")
                time.sleep(2)

        else:
            # If all retries for this model failed on non-404, try next candidate
            _ACTIVE_MODEL_INDEX += 1

    return None


def should_skip_classification(item: Dict[str, Any]) -> bool:
    """Check if item is already properly classified."""
    if item.get("classified_by") == "manual" or item.get("custom_classified") is True:
        return True

    # If already classified by Gemini and has real name
    name = item.get("name", "")
    is_generic = name.startswith("Wallpaper #") or name.startswith("Live Wallpaper #")
    is_generic_cat = item.get("category", "") in ("images", "unknown", "")

    if item.get("classified_by") == "gemini" and not is_generic and not is_generic_cat:
        return True

    # Simple AI items should be upgraded by Gemini
    if item.get("classified_by") == "simple_ai":
        return False

    # If it has rich search terms and is not generic
    search_terms = item.get("search_terms")
    if search_terms and len(search_terms) > 3 and not is_generic and not is_generic_cat:
        return True

    return False


def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    if not os.path.exists(CATALOG_PATH):
        print(f"Error: {CATALOG_PATH} not found.")
        sys.exit(1)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    wallpapers = catalog.get("wallpapers", [])
    print(f"Loaded {len(wallpapers)} wallpapers from catalog.")

    existing_cat_ids = {c["id"] for c in STANDARD_CATEGORIES}
    categories_dict = {c["id"]: c for c in STANDARD_CATEGORIES}

    MAX_PER_RUN = int(os.environ.get("MAX_CLASSIFY_PER_RUN", "30"))
    updated_count = 0
    consecutive_failures = 0
    total = len(wallpapers)

    # Filter unclassified candidates
    candidates = [w for w in wallpapers if not should_skip_classification(w)]
    print(f"Wallpapers needing classification: {len(candidates)} (batch limit: {MAX_PER_RUN})")

    if not candidates:
        print("All wallpapers are already well-classified. Nothing to do!")
        return

    for idx, item in enumerate(candidates[:MAX_PER_RUN]):
        item_id = item["id"]
        image_bytes = fetch_image_bytes(item)
        if not image_bytes:
            print(f" -> Skipping {item_id}: could not load image bytes.")
            continue

        active_model = get_candidate_models(GEMINI_API_KEY)[min(_ACTIVE_MODEL_INDEX, len(get_candidate_models(GEMINI_API_KEY)) - 1)]
        print(f"[{updated_count+1}/{MAX_PER_RUN}] Classifying {item_id} with Gemini ({active_model})...")
        result = analyze_image_with_gemini(image_bytes, GEMINI_API_KEY)

        if result:
            name = result.get("name", item["name"]).strip()
            cat = result.get("category", "abstract").lower().strip()
            color = result.get("primary_color", item.get("primary_color", "#121212"))
            search_terms = result.get("search_terms", [])
            tags = result.get("tags", search_terms[:5])

            is_video = item.get("type") == "video" or item.get("is_live", False)
            if is_video:
                assigned_cat = "live"
                if "live wallpaper" not in search_terms:
                    search_terms.insert(0, "live wallpaper")
            else:
                assigned_cat = cat

            item["name"] = name
            item["category"] = assigned_cat
            item["primary_color"] = color
            item["search_terms"] = search_terms
            item["tags"] = list(dict.fromkeys(tags))
            item["classified_by"] = "gemini"

            if assigned_cat not in existing_cat_ids:
                label = assigned_cat.replace("_", " ").capitalize()
                categories_dict[assigned_cat] = {"id": assigned_cat, "label": label}
                existing_cat_ids.add(assigned_cat)

            updated_count += 1
            print(f" -> '{name}' | Categoria: {assigned_cat} | Cor: {color} | Tags: {', '.join(item['tags'][:4])}")

            # Progressive save
            catalog["categories"] = list(categories_dict.values())
            catalog["wallpapers"] = wallpapers
            with open(CATALOG_PATH, "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2, ensure_ascii=False)
                f.write("\n")

            consecutive_failures = 0
            time.sleep(3.5)
        else:
            print(f" -> Skipping {item_id} due to API error.")
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print("Multiple consecutive API failures or quota exhaustion. Stopping batch gracefully.")
                break
            time.sleep(5.0)

    catalog["categories"] = list(categories_dict.values())
    catalog["wallpapers"] = wallpapers
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nSuccessfully categorized {updated_count} wallpapers with Gemini Flash!")


if __name__ == "__main__":
    main()
