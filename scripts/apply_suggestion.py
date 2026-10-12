import json
import os
import re
import sys


def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    if not issue_body:
        print("Error: ISSUE_BODY environment variable is empty.")
        sys.exit(1)

    # Search for json block in issue body
    match = re.search(r"```json\s*(\{.*?\})\s*```", issue_body, re.DOTALL)
    if not match:
        print("Error: No structured JSON code block found in issue body.")
        sys.exit(1)

    try:
        data = json.loads(match.group(1))
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)

    wallpaper_id = data.get("id")
    new_name = data.get("name")
    new_tags = data.get("tags", [])

    if not wallpaper_id:
        print("Error: 'id' field is missing in JSON.")
        sys.exit(1)

    catalog_path = "wallpapers/catalog.json"
    if not os.path.exists(catalog_path):
        print(f"Error: {catalog_path} not found.")
        sys.exit(1)

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    wallpapers = catalog.get("wallpapers", [])
    target = None
    for item in wallpapers:
        if item.get("id") == wallpaper_id:
            target = item
            break

    if not target:
        print(f"Error: Wallpaper '{wallpaper_id}' not found in catalog.")
        sys.exit(1)

    # Update name if provided
    if new_name and isinstance(new_name, str) and new_name.strip():
        target["name"] = new_name.strip()

    # Merge tags and search_terms preserving order without duplicates
    current_tags = target.get("tags", [])
    current_search_terms = target.get("search_terms", [])

    for tag in new_tags:
        if not isinstance(tag, str):
            continue
        cleaned = tag.strip().lower()
        if cleaned:
            if cleaned not in [t.lower() for t in current_tags]:
                current_tags.append(tag.strip())
            if cleaned not in [s.lower() for s in current_search_terms]:
                current_search_terms.append(tag.strip())

    target["tags"] = current_tags
    target["search_terms"] = current_search_terms

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Successfully applied suggestions for wallpaper {wallpaper_id}!")


if __name__ == "__main__":
    main()
