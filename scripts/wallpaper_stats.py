#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Script to calculate and publish daily wallpaper repository statistics:
- Total storage used (GB and MB) for full wallpapers, thumbnails, and total repo.
- Total wallpaper count (images and live videos).
- Description classification breakdown (Google Gemini AI, Simple AI, Manual, and Pending).
- Category distribution.
- Updates README.md and outputs to GITHUB_STEP_SUMMARY.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "wallpapers", "catalog.json")
README_PATH = os.path.join(BASE_DIR, "README.md")
FULL_DIR = os.path.join(BASE_DIR, "wallpapers", "full")
THUMB_DIR = os.path.join(BASE_DIR, "wallpapers", "thumbnails")

DEFAULT_REPO = os.environ.get("GITHUB_REPOSITORY", "S-Marcos-S/viagara-wallpapers")
DEFAULT_BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def load_catalog() -> Dict[str, Any]:
    if not os.path.exists(CATALOG_PATH):
        print(f"Error: Catalog not found at {CATALOG_PATH}")
        sys.exit(1)
    with open(CATALOG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def calculate_local_dir_size(path: str) -> Tuple[int, int]:
    """Returns (total_bytes, file_count) for a directory on disk."""
    if not os.path.exists(path):
        return 0, 0
    total_bytes = 0
    count = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                total_bytes += os.path.getsize(fp)
                count += 1
    return total_bytes, count


def fetch_sizes_from_github_api(repo: str, branch: str = "main") -> Dict[str, Any]:
    """
    Fetches exact blob sizes recursively from GitHub Git Trees API in 1 request.
    Works perfectly even with sparse checkout or shallow clones!
    """
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    headers = {
        "User-Agent": "Viagara-Wallpaper-Stats",
        "Accept": "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Warning: Could not fetch Git tree from GitHub API ({e}).")
        return {}

    full_bytes = 0
    full_count = 0
    thumb_bytes = 0
    thumb_count = 0
    total_bytes = 0
    total_count = 0

    for item in data.get("tree", []):
        size = item.get("size", 0)
        path = item.get("path", "")
        if item.get("type") == "blob":
            total_bytes += size
            total_count += 1
            if path.startswith("wallpapers/full/"):
                full_bytes += size
                full_count += 1
            elif path.startswith("wallpapers/thumbnails/"):
                thumb_bytes += size
                thumb_count += 1

    return {
        "full_bytes": full_bytes,
        "full_count": full_count,
        "thumb_bytes": thumb_bytes,
        "thumb_count": thumb_count,
        "total_bytes": total_bytes,
        "total_count": total_count,
    }


def get_storage_stats() -> Dict[str, Any]:
    # 1. Try local disk first
    full_bytes, full_count = calculate_local_dir_size(FULL_DIR)
    thumb_bytes, thumb_count = calculate_local_dir_size(THUMB_DIR)
    total_bytes, total_count = calculate_local_dir_size(BASE_DIR)

    # 2. If local files are empty (sparse checkout), fallback to GitHub API
    if full_count == 0 or full_bytes == 0:
        print("Notice: Local directory appears sparse or empty. Querying GitHub Git Trees API...")
        api_stats = fetch_sizes_from_github_api(DEFAULT_REPO, DEFAULT_BRANCH)
        if api_stats:
            return api_stats

    return {
        "full_bytes": full_bytes,
        "full_count": full_count,
        "thumb_bytes": thumb_bytes,
        "thumb_count": thumb_count,
        "total_bytes": total_bytes,
        "total_count": total_count,
    }


def bytes_to_human(b: int) -> str:
    gb = b / (1024 ** 3)
    mb = b / (1024 ** 2)
    if gb >= 1.0:
        return f"{gb:.2f} GB ({mb:.1f} MB)"
    return f"{mb:.1f} MB ({gb:.3f} GB)"


def analyze_catalog(catalog: Dict[str, Any]) -> Dict[str, Any]:
    wallpapers = catalog.get("wallpapers", [])
    total_wallpapers = len(wallpapers)

    by_classification = {
        "gemini": 0,
        "simple_ai": 0,
        "manual": 0,
        "sem_descricao": 0,
    }

    by_type = {
        "image": 0,
        "video": 0,
    }

    by_category: Dict[str, int] = {}

    for w in wallpapers:
        # Classification
        cb = w.get("classified_by")
        custom = w.get("custom_classified")
        if custom is True or cb == "manual":
            by_classification["manual"] += 1
        elif cb == "gemini":
            by_classification["gemini"] += 1
        elif cb == "simple_ai":
            by_classification["simple_ai"] += 1
        else:
            by_classification["sem_descricao"] += 1

        # Type
        is_video = w.get("type") == "video" or w.get("is_live", False)
        if is_video:
            by_type["video"] += 1
        else:
            by_type["image"] += 1

        # Category
        cat = w.get("category", "outros")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total": total_wallpapers,
        "classification": by_classification,
        "types": by_type,
        "categories": by_category,
    }


def generate_stats_markdown(storage: Dict[str, Any], catalog_stats: Dict[str, Any]) -> str:
    tz_brt = timezone(timedelta(hours=-3))
    now_brt = datetime.now(tz_brt).strftime("%d/%m/%Y às %H:%M (Horário de Brasília)")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_wallpapers = catalog_stats["total"]
    classes = catalog_stats["classification"]
    types = catalog_stats["types"]
    cats = catalog_stats["categories"]

    def pct(val: int) -> float:
        return (val / total_wallpapers * 100) if total_wallpapers > 0 else 0.0

    full_gb = storage["full_bytes"] / (1024 ** 3)
    full_mb = storage["full_bytes"] / (1024 ** 2)
    thumb_mb = storage["thumb_bytes"] / (1024 ** 2)
    thumb_gb = storage["thumb_bytes"] / (1024 ** 3)
    repo_gb = storage["total_bytes"] / (1024 ** 3)
    repo_mb = storage["total_bytes"] / (1024 ** 2)

    gemini_pct = pct(classes['gemini'])
    simple_pct = pct(classes['simple_ai'])
    manual_pct = pct(classes['manual'])
    pending_pct = pct(classes['sem_descricao'])

    lines = [
        "<!-- START_WALLPAPER_STATS -->",
        "## 📊 Painel de Estatísticas Diárias do Repositório",
        "",
        f"> 🕒 **Última atualização:** {now_brt} (`{now_utc}`)",
        "",
        "### 💾 Armazenamento e Consumo em Disco",
        "",
        "| Diretório / Recurso | Tamanho em Gigabytes | Tamanho em Megabytes | Arquivos |",
        "| :--- | :---: | :---: | :---: |",
        f"| 📁 **Wallpapers em Alta Resolução (`wallpapers/full/`)** | **{full_gb:.3f} GB** | {full_mb:.1f} MB | {storage['full_count']} |",
        f"| 🖼️ **Miniaturas Otimizadas (`wallpapers/thumbnails/`)** | **{thumb_gb:.3f} GB** | {thumb_mb:.1f} MB | {storage['thumb_count']} |",
        f"| 📦 **Total do Repositório** | **{repo_gb:.3f} GB** | **{repo_mb:.1f} MB** | {storage['total_count']} |",
        "",
        "### 🤖 Status das Descrições e Classificação por IA",
        "",
        "| Método de Descrição | Quantidade | Porcentagem | Barra de Progresso |",
        "| :--- | :---: | :---: | :--- |",
        f"| ✨ **IA Avançada (Google Gemini)** | **{classes['gemini']}** | **{gemini_pct:.1f}%** | `{'█' * int(gemini_pct // 5)}{'░' * (20 - int(gemini_pct // 5))}` |",
        f"| 🤖 **IA Simples (MobileNetV3 / Local)** | **{classes['simple_ai']}** | **{simple_pct:.1f}%** | `{'█' * int(simple_pct // 5)}{'░' * (20 - int(simple_pct // 5))}` |",
        f"| ✍️ **Curadoria Manual (Humana)** | **{classes['manual']}** | **{manual_pct:.1f}%** | `{'█' * int(manual_pct // 5)}{'░' * (20 - int(manual_pct // 5))}` |",
        f"| ⏳ **Pendentes / Sem Descrição** | **{classes['sem_descricao']}** | **{pending_pct:.1f}%** | `{'█' * int(pending_pct // 5)}{'░' * (20 - int(pending_pct // 5))}` |",
        f"| 🎯 **Total Geral no Catálogo** | **{total_wallpapers}** | **100%** | |",
        "",
        "### 🎬 Tipos de Papéis de Parede",
        "",
        f"- 🖼️ **Imagens Estáticas (WebP / JPG):** **{types['image']}** ({pct(types['image']):.1f}%)",
        f"- 🎥 **Live Wallpapers / Vídeos (MP4):** **{types['video']}** ({pct(types['video']):.1f}%)",
        "",
        "### 🏷️ Distribuição por Categorias",
        "",
        "| Categoria | Quantidade | Proporção |",
        "| :--- | :---: | :---: |",
    ]

    for cat_id, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
        label = cat_id.replace("_", " ").capitalize()
        lines.append(f"| `{label}` | **{count}** | {pct(count):.1f}% |")

    lines.append("")
    lines.append("<!-- END_WALLPAPER_STATS -->")
    return "\n".join(lines)


def update_readme(stats_md: str):
    header = (
        "# 🌌 Viagara Wallpapers Repository\n\n"
        "Repositório oficial de papéis de parede estáticos e dinâmicos (Live Wallpapers) em alta definição "
        "para o **Viagara Launcher**.\n\n"
        "Os papéis de parede são curados, sincronizados e categorizados automaticamente através de fluxos de "
        "Inteligência Artificial (Google Gemini Flash & Simple AI Vision) e curadoria da comunidade.\n\n"
        "---\n\n"
    )

    if not os.path.exists(README_PATH):
        content = header + stats_md + "\n"
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created new {README_PATH}")
        return

    with open(README_PATH, "r", encoding="utf-8") as f:
        existing = f.read()

    start_tag = "<!-- START_WALLPAPER_STATS -->"
    end_tag = "<!-- END_WALLPAPER_STATS -->"

    if start_tag in existing and end_tag in existing:
        before = existing.split(start_tag)[0]
        after = existing.split(end_tag)[1]
        new_content = before + stats_md + after
    else:
        new_content = existing.rstrip() + "\n\n" + stats_md + "\n"

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Updated {README_PATH}")


def write_step_summary(stats_md: str):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(stats_md + "\n")
        print(f"Appended stats to GITHUB_STEP_SUMMARY: {summary_path}")


def main():
    print("=== Generating Daily Wallpaper Repository Statistics ===")
    catalog = load_catalog()
    catalog_stats = analyze_catalog(catalog)
    storage_stats = get_storage_stats()

    stats_md = generate_stats_markdown(storage_stats, catalog_stats)

    update_readme(stats_md)
    write_step_summary(stats_md)

    print("\n--- Summary Preview ---")
    print(f"Total Wallpapers: {catalog_stats['total']}")
    print(f"Storage: {bytes_to_human(storage_stats['total_bytes'])}")
    print(f"Gemini: {catalog_stats['classification']['gemini']}")
    print(f"Simple AI: {catalog_stats['classification']['simple_ai']}")
    print(f"Manual: {catalog_stats['classification']['manual']}")
    print(f"Pending: {catalog_stats['classification']['sem_descricao']}")
    print("-----------------------")


if __name__ == "__main__":
    main()
