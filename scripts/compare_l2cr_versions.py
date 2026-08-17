"""Compare L2-CR-001 repository version with L2-CR-002 revised source."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLD_PATH = PROJECT_ROOT / "knowledge" / "curated" / "healthcoach_correlation_modeling.md"
REVISED_PATH = Path(
    r"C:\Users\14042\Desktop\AI Health Coach App_Piyu\RAG Docs\LC 2R V2\LC 2R\healthcoach_correlation_modeling_REVISED.md"
)


def count_catalogue_rows(text: str) -> int:
    return len(re.findall(r"^\|[^|\n]+→[^|\n]+\|", text, re.MULTILINE))


def count_active_relationships(text: str) -> int:
    return len(re.findall(r"^\| R-\d{2} \|", text, re.MULTILINE))


def count_deferred(text: str) -> int:
    return len(re.findall(r"^\| D-\d{2} \|", text, re.MULTILINE))


def count_removed(text: str) -> int:
    return len(re.findall(r"^\| X-\d{2} \|", text, re.MULTILINE))


def count_arrows(text: str) -> int:
    return len(re.findall(r"→", text))


def extract_source_keys(text: str) -> set[str]:
    keys: set[str] = set()
    if text.lstrip().startswith("---"):
        front = text.split("---", 2)[1]
        match = re.search(r"source_keys:\s*\[(.*?)\]", front, re.DOTALL)
        if match:
            keys.update(re.findall(r"[A-Za-z0-9_-]+", match.group(1)))
    keys.update(re.findall(r"\[([A-Za-z0-9_-]+(?:,\s*[A-Za-z0-9_-]+)*)\]", text))
    return {key.strip() for key in keys if key.strip() and not key.startswith("rhr")}


def main() -> None:
    old_text = OLD_PATH.read_text(encoding="utf-8")
    new_text = REVISED_PATH.read_text(encoding="utf-8")

    print("L2-CR DIFF SUMMARY")
    print("=" * 72)
    print(f"old_chars: {len(old_text)}")
    print(f"new_chars: {len(new_text)}")
    print(f"old_catalogue_rows: {count_catalogue_rows(old_text)}")
    print(f"new_active_relationships: {count_active_relationships(new_text)}")
    print(f"new_deferred: {count_deferred(new_text)}")
    print(f"new_removed: {count_removed(new_text)}")
    print(f"old_arrow_count: {count_arrows(old_text)}")
    print(f"new_arrow_count: {count_arrows(new_text)}")
    print(f"old_source_keys_frontmatter: {re.search(r'sources: \\[(.*?)\\]', old_text.split('---', 2)[1] if old_text.startswith('---') else '')}")
    old_keys = set(re.findall(r"sources: \[(.*?)\]", old_text.split("---", 2)[1])[0].split(",")) if old_text.startswith("---") else set()
    old_keys = {k.strip() for k in old_keys}
    new_keys_match = re.search(r"source_keys: \[(.*?)\]", new_text.split("---", 2)[1], re.DOTALL)
    new_keys = {k.strip() for k in new_keys_match.group(1).replace("\n", " ").split(",")} if new_keys_match else set()
    print(f"old_source_keys: {sorted(old_keys)}")
    print(f"new_source_keys: {sorted(new_keys)}")
    print(f"added_source_keys: {sorted(new_keys - old_keys)}")
    print(f"removed_source_keys: {sorted(old_keys - new_keys)}")


if __name__ == "__main__":
    main()
