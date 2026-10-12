#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
AI Wallpaper Classifier using Google Gemini 1.5 Flash.
Analyzes wallpaper thumbnails to determine:
- Accurate character/scene/subject title
- Semantic category (anime, games, nature, cars, space, minimal, abstract, etc.)
- Rich search terms in Portuguese & English for instant search in the launcher
- Primary dominant color hex
"""

import os
import sys
import json
import base64
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

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

PROMPT = """Você é um especialista em classificação e catalogação visual de papéis de parede mobile para um aplicativo Android.
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


def analyze_image_with_gemini(image_path: str, api_key: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(image_path):
        return None

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        b64_img = base64.b64encode(image_bytes).decode("utf-8")

        # List of candidate models in order of priority (uses current active models with automatic fallback)
        CANDIDATE_MODELS = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
        ]

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/webp",
                                "data": b64_img
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }

        for model_name in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))

                text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Clean potential markdown wrapping
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]

                return json.loads(text.strip())
            except urllib.error.HTTPError as e:
                # If model is not found / deprecated (404), try next model in CANDIDATE_MODELS
                if e.code == 404:
                    print(f"Model {model_name} not found or retired, trying next model...")
                    continue
                elif e.code == 429:
                    print(f"Rate limited on {model_name}. Waiting 10s...")
                    time.sleep(10)
                    return None
                else:
                    print(f"HTTP error {e.code} on {model_name}: {e.read().decode('utf-8')}")
                    continue
        return None
    except urllib.error.HTTPError as e:
        print(f"Gemini API HTTP Error {e.code}: {e.read().decode('utf-8')}")
        if e.code == 429:
            print("Rate limit reached. Waiting 10s...")
            time.sleep(10)
        return None
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return None


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

    # Track discovered categories
    existing_cat_ids = {c["id"] for c in STANDARD_CATEGORIES}
    categories_dict = {c["id"]: c for c in STANDARD_CATEGORIES}

    updated_count = 0
    total = len(wallpapers)

    for idx, item in enumerate(wallpapers):
        item_id = item["id"]
        # Skip if already categorized with rich search terms and not generic
        if item.get("search_terms") and not item["name"].startswith("Wallpaper #"):
            continue

        thumb_path = os.path.join(THUMB_DIR, f"{item_id}.webp")
        if not os.path.exists(thumb_path):
            continue

        print(f"[{idx+1}/{total}] Classifying {item_id} with Gemini Flash...")
        result = analyze_image_with_gemini(thumb_path, GEMINI_API_KEY)

        if result:
            name = result.get("name", item["name"]).strip()
            cat = result.get("category", "abstract").lower().strip()
            color = result.get("primary_color", item.get("primary_color", "#121212"))
            search_terms = result.get("search_terms", [])

            # Keep video items categorized or tagged as live
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
            item["tags"] = list(dict.fromkeys(search_terms[:5]))

            # Register category if new
            if assigned_cat not in existing_cat_ids:
                label = assigned_cat.replace("_", " ").capitalize()
                categories_dict[assigned_cat] = {"id": assigned_cat, "label": label}
                existing_cat_ids.add(assigned_cat)

            updated_count += 1
            print(f" -> '{name}' | Categoria: {assigned_cat} | Tags: {', '.join(search_terms[:4])}")

            # Sleep slightly to stay comfortably within rate limits
            time.sleep(2.0)
        else:
            print(f" -> Failed to classify {item_id}, keeping existing metadata.")

    catalog["categories"] = list(categories_dict.values())
    catalog["wallpapers"] = wallpapers

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nSuccessfully categorized {updated_count} wallpapers with Gemini 1.5 Flash!")


if __name__ == "__main__":
    main()
