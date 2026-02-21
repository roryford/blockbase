#!/usr/bin/env python3
"""
generate_index.py — Regenerates blocks/index.json from blocks/ and patterns/ contents.

Auto-extracts: file, topic (first H1), date (from content), summary (first body paragraph).
Auto-extracts from YAML frontmatter (if present): claims, confidence, staleness_risk, connected_blocks, theory_delta, environment_scope.
Preserves: categories from existing index.json (manual classification).
Auto-derives: connections (scans for cross-references to other block filenames).
Flags: files in index.json that no longer exist on disk.

Usage:
    python scripts/generate_index.py
    python scripts/generate_index.py --dry-run
"""

import json
import re
import sys
from datetime import date as dt
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
BLOCKS_DIR = REPO_ROOT / "blocks"
PATTERNS_DIR = REPO_ROOT / "patterns"
INDEX_PATH = BLOCKS_DIR / "index.json"


def extract_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter block if present. Returns {} if absent or malformed."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        fm = yaml.safe_load(text[3:end])
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block from text, returning the rest."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip("\n")


def extract_metadata(filepath: Path) -> dict:
    raw = filepath.read_text(encoding="utf-8")
    fm = extract_frontmatter(raw)
    text = strip_frontmatter(raw)
    lines = text.splitlines()

    topic = None
    date = None
    summary = None

    # Topic: first H1
    for line in lines:
        if line.startswith("# "):
            topic = line[2:].strip()
            break

    # Date: prefer frontmatter 'date' field, fall back to *Researched: DATE* body patterns
    if fm.get("date"):
        date = str(fm["date"])
    else:
        date_match = re.search(r'\*\w+:\s*(\d{4}-\d{2}-\d{2})', text)
        if date_match:
            date = date_match.group(1)

    # Summary: first non-empty paragraph after the H1 and date line
    in_body = False
    para_lines = []
    for line in lines:
        if line.startswith("# "):
            in_body = True
            continue
        if not in_body:
            continue
        if re.match(r'^\*\w+:', line.strip()):
            continue
        if not line.strip() and not para_lines:
            continue
        if not line.strip() and para_lines:
            break
        if line.startswith("#"):
            if para_lines:
                break
            continue
        para_lines.append(line.strip())

    if para_lines:
        summary = " ".join(para_lines)
        if len(summary) > 220:
            summary = summary[:217] + "..."

    return {
        "topic": topic or filepath.stem,
        "date": date,
        "summary": summary or "",
        "categories": fm.get("categories", []),
        "claims": fm.get("claims", []),
        "confidence": fm.get("confidence"),
        "staleness_risk": fm.get("staleness_risk"),
        "connected_blocks": fm.get("connected_blocks", []),
        "theory_delta": fm.get("theory_delta"),
        "environment_scope": fm.get("environment_scope"),
        # internal: True suppresses a block from user-facing query results.
        # It does NOT hide the block from the public index.json or the repo.
        # Use for implementation blocks that would pollute queries about unrelated topics.
        "internal": fm.get("internal", False),
    }


def extract_connections(filepath: Path, all_files: set) -> list:
    """Scan file text for references to other block/pattern filenames."""
    text = filepath.read_text(encoding="utf-8")
    found = set()
    for filename in all_files:
        if filename == filepath.name:
            continue
        stem = Path(filename).stem
        # Match hyphenated stem (e.g., "skills-ecosystem")
        if re.search(r'\b' + re.escape(stem) + r'\b', text):
            found.add(filename)
            continue
        # Also match natural-language form with hyphens as spaces (e.g., "skills ecosystem")
        natural = stem.replace("-", " ")
        if natural != stem and re.search(
            r'\b' + re.escape(natural) + r'\b', text, re.IGNORECASE
        ):
            found.add(filename)
    return sorted(found)


def load_existing(path: Path) -> dict:
    if not path.exists():
        return {"blocks": {}, "patterns": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "blocks": {e["file"]: e for e in data.get("blocks", [])},
        "patterns": {e["file"]: e for e in data.get("patterns", [])},
    }


def process_dir(dirpath: Path, kind: str, existing: dict, all_files: set) -> list:
    existing_kind = existing.get(kind, {})
    entries = []

    for filepath in sorted(dirpath.glob("*.md")):
        if filepath.name in ("index.md",):
            continue
        meta = extract_metadata(filepath)
        prev = existing_kind.get(filepath.name, {})

        entry = {
            "file": filepath.name,
            "topic": meta["topic"],
            "date": meta["date"],
            # Preserve manual categories from index if meaningful; fall back to frontmatter, then unclassified
            "categories": (
                prev.get("categories")
                if prev.get("categories") and prev["categories"] != ["unclassified"]
                else meta.get("categories") or ["unclassified"]
            ),
            # Preserve manual connections if set; auto-derive only for new files
            "connections": prev.get("connections") or extract_connections(filepath, all_files),
            "summary": meta["summary"] or prev.get("summary", ""),
            # Frontmatter-derived fields (omitted if empty)
            **( {"claims": meta["claims"]} if meta["claims"] else {} ),
            **( {"confidence": meta["confidence"]} if meta["confidence"] else {} ),
            **( {"staleness_risk": meta["staleness_risk"]} if meta["staleness_risk"] else {} ),
            **( {"connected_blocks": meta["connected_blocks"]} if meta["connected_blocks"] else {} ),
            **( {"theory_delta": meta["theory_delta"]} if meta["theory_delta"] else {} ),
            **( {"environment_scope": meta["environment_scope"]} if meta["environment_scope"] else {} ),
            # Omit 'internal' key entirely when False -- sparse representation.
            **( {"internal": True} if meta["internal"] else {} ),
        }
        entries.append(entry)

    for filename in existing_kind:
        if not (dirpath / filename).exists():
            print(f"  WARNING: {filename} in index but not on disk", file=sys.stderr)

    return entries


def main():
    dry_run = "--dry-run" in sys.argv

    all_files = set()
    for d in [BLOCKS_DIR, PATTERNS_DIR]:
        for f in d.glob("*.md"):
            if f.name != "index.md":
                all_files.add(f.name)

    existing = load_existing(INDEX_PATH)

    blocks = process_dir(BLOCKS_DIR, "blocks", existing, all_files)
    patterns = process_dir(PATTERNS_DIR, "patterns", existing, all_files)

    index = {
        "generated": str(dt.today()),
        "version": "2",
        "blocks": blocks,
        "patterns": patterns,
    }

    output = json.dumps(index, indent=2)

    if dry_run:
        print(output)
    else:
        INDEX_PATH.write_text(output, encoding="utf-8")
        print(f"Written {INDEX_PATH}")

    new_b = [e["file"] for e in blocks if e["file"] not in existing["blocks"]]
    new_p = [e["file"] for e in patterns if e["file"] not in existing["patterns"]]
    print(f"  {len(blocks)} blocks, {len(patterns)} patterns")
    if new_b:
        print(f"  New blocks: {', '.join(new_b)}")
    if new_p:
        print(f"  New patterns: {', '.join(new_p)}")


if __name__ == "__main__":
    main()
