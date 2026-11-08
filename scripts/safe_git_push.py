#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Resilient Git Commit & Push helper for CI/CD:
Automatically handles concurrent remote commits without line-based merge conflicts
by cleanly merging JSON catalog entries on top of the latest origin/main.
"""

import os
import sys
import json
import time
import subprocess
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(BASE_DIR, "wallpapers", "catalog.json")
README_PATH = os.path.join(BASE_DIR, "README.md")


def run(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"[Git] $ {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=BASE_DIR, text=True, capture_output=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr and res.returncode != 0:
        print(f"[Git Error] {res.stderr.strip()}", file=sys.stderr)
    if check and res.returncode != 0:
        raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
    return res


def extract_new_issue_items(issue_number: str) -> List[Dict[str, Any]]:
    """Find catalog items belonging to the given issue."""
    if not os.path.exists(CATALOG_PATH):
        return []
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)
        prefix = f"wp_i{issue_number}_"
        return [w for w in cat.get("wallpapers", []) if w.get("id", "").startswith(prefix)]
    except Exception as e:
        print(f"[Git] Error reading local catalog: {e}")
        return []


def merge_items_into_catalog(new_items: List[Dict[str, Any]]) -> bool:
    """Inserts new items at the top of catalog.json without duplicates."""
    if not os.path.exists(CATALOG_PATH):
        return False
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)

        wallpapers = cat.get("wallpapers", [])
        existing_ids = {w["id"] for w in wallpapers}

        added = 0
        for it in reversed(new_items):
            item_id = it.get("id")
            if item_id and item_id not in existing_ids:
                wallpapers.insert(0, it)
                existing_ids.add(item_id)
                added += 1

        cat["wallpapers"] = wallpapers
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(cat, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"[Git] Merged {added} issue items into catalog.json.")
        return True
    except Exception as e:
        print(f"[Git] Error merging into catalog: {e}")
        return False


def main():
    issue_number = os.environ.get("ISSUE_NUM", "").strip() or os.environ.get("ISSUE_NUMBER", "").strip()
    if not issue_number:
        print("[Git] Missing ISSUE_NUM or ISSUE_NUMBER environment variable.")
        sys.exit(1)

    max_retries = int(os.environ.get("MAX_RETRIES", "5"))

    # Configure bot identity
    run('git config user.name "github-actions[bot]"')
    run('git config user.email "41898282+github-actions[bot]@users.noreply.github.com"')

    new_items = extract_new_issue_items(issue_number)
    print(f"[Git] Found {len(new_items)} items for Issue #{issue_number} in local catalog.")

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Commit & Push Attempt {attempt}/{max_retries} ---")
        try:
            # 1. Fetch remote origin
            run("git fetch origin main")

            # 2. Check if remote origin/main has advanced
            remote_rev = run("git rev-parse origin/main").stdout.strip()
            head_rev = run("git rev-parse HEAD").stdout.strip()

            if remote_rev != head_rev:
                print(f"[Git] Remote is ahead ({remote_rev[:7]} vs {head_rev[:7]}). Harmonizing catalog with remote...")
                # Reset catalog.json and README to remote state
                run("git checkout origin/main -- wallpapers/catalog.json wallpapers/notification.json README.md", check=False)
                # Re-merge our new issue items cleanly in Python
                merge_items_into_catalog(new_items)
                # Recalculate stats
                run("python scripts/wallpaper_stats.py", check=False)

            # 3. Check if there are changes to commit
            status = run("git status --porcelain wallpapers/ README.md").stdout.strip()
            if not status:
                print("[Git] No changes detected to commit. Everything is already up to date.")
                sys.exit(0)

            # 4. Stage and commit
            run("git add wallpapers/ README.md")
            commit_msg = f"feat(wallpapers): add wallpapers from issue #{issue_number} [skip ci]"
            run(f'git commit -m "{commit_msg}"')

            # 5. Push
            push_res = run("git push origin main", check=False)
            if push_res.returncode == 0:
                print(f"🎉 Successfully committed and pushed wallpapers from issue #{issue_number}!")
                sys.exit(0)

            print(f"[Git] Push rejected on attempt {attempt}. Retrying in 2 seconds...")
            # Reset the commit to try again with fresh remote
            run("git reset --soft HEAD~1", check=False)
            time.sleep(2.0)

        except Exception as e:
            print(f"[Git Attempt Error] {e}")
            time.sleep(2.0)

    print(f"[Git] Error: Failed to push changes after {max_retries} attempts.")
    sys.exit(1)


if __name__ == "__main__":
    main()
