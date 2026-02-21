#!/usr/bin/env python3
"""Validate block format for CI format gate.

Usage:
    python scripts/validate_blocks.py blocks/foo.md blocks/bar.md
    # or pipe a list of files from git diff

Rules:
    - If a block has YAML frontmatter, it must be well-formed
    - Required for all blocks with frontmatter: confidence
    - Required for high-confidence blocks (empirical | validated): staleness_risk
    - claims: always a warning if missing (not yet migrated to formal claims lists)
    - All other blocks: missing staleness_risk produces a warning, not an error
    - confidence must be one of: empirical | validated | secondary-research | inferred |
      medium | theoretical | draft | mixed | verified
    - staleness_risk must be: low | medium | high
    - Blocks without frontmatter get a warning, not an error
"""

import sys
import os
import re

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)

REQUIRED_FIELDS = {"confidence"}
HIGH_CONFIDENCE = {"empirical", "validated"}
VALID_CONFIDENCE = {
    "empirical", "validated", "secondary-research", "inferred",
    "medium", "theoretical", "draft", "mixed", "verified",
}
VALID_STALENESS = {"low", "medium", "high"}
VALID_KNOWLEDGE_TYPE = {"validated", "observed", "theoretical"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def validate_block(path):
    errors = []
    warnings = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        errors.append(f"{path}: cannot read file: {e}")
        return errors, warnings

    if not content.startswith("---\n"):
        warnings.append(f"no YAML frontmatter (add frontmatter to improve block quality)")
        return errors, warnings

    match = FRONTMATTER_RE.match(content)
    if not match:
        errors.append(f"malformed frontmatter -- missing closing ---")
        return errors, warnings

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        errors.append(f"invalid YAML in frontmatter: {e}")
        return errors, warnings

    if not isinstance(fm, dict):
        errors.append(f"frontmatter must be a YAML mapping, got {type(fm).__name__}")
        return errors, warnings

    missing = REQUIRED_FIELDS - fm.keys()
    if missing:
        errors.append(f"missing required frontmatter fields: {sorted(missing)}")

    confidence = fm.get("confidence")

    if confidence is not None and confidence not in VALID_CONFIDENCE:
        errors.append(
            f"confidence '{confidence}' invalid -- must be one of: {sorted(VALID_CONFIDENCE)}"
        )

    if "staleness_risk" in fm and fm["staleness_risk"] not in VALID_STALENESS:
        errors.append(
            f"staleness_risk '{fm['staleness_risk']}' invalid -- must be one of: {sorted(VALID_STALENESS)}"
        )

    is_high_confidence = confidence in HIGH_CONFIDENCE

    if "staleness_risk" not in fm:
        if is_high_confidence:
            errors.append("missing staleness_risk -- required for empirical/validated blocks")
        else:
            warnings.append("missing staleness_risk (required for empirical/validated blocks)")

    if "knowledge_type" not in fm:
        warnings.append(
            "missing knowledge_type field (validated | observed | theoretical) -- block treated as theoretical"
        )
    elif fm["knowledge_type"] not in VALID_KNOWLEDGE_TYPE:
        warnings.append(
            f"invalid knowledge_type '{fm['knowledge_type']}', must be: validated | observed | theoretical"
        )

    if "claims" not in fm:
        warnings.append("missing claims list (add empirical claims for full block quality)")
    elif not isinstance(fm["claims"], list):
        errors.append(f"claims must be a list, got {type(fm['claims']).__name__}")
    elif len(fm["claims"]) == 0:
        warnings.append("claims list is empty")

    return errors, warnings


def main():
    files = [f for f in sys.argv[1:] if f.endswith(".md")]

    if not files:
        print("No block files to validate.")
        sys.exit(0)

    total_errors = 0
    total_warnings = 0

    for path in files:
        if not os.path.exists(path):
            continue  # deleted file -- skip

        errors, warnings = validate_block(path)

        for w in warnings:
            print(f"  WARN  {path}: {w}")
            total_warnings += 1

        for e in errors:
            print(f"  FAIL  {path}: {e}")
            total_errors += 1

        if not errors and not warnings:
            print(f"  OK    {path}")

    print(
        f"\n{len(files)} blocks checked -- "
        f"{total_errors} error(s), {total_warnings} warning(s)"
    )

    if total_errors:
        print("\nFix errors above before merging.")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
