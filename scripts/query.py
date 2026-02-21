#!/usr/bin/env python3
"""
Blockbase local query -- keyword/fuzzy search over blocks/index.json.
Usage: python scripts/query.py "your question here" [--json]

Dependencies: pip install rank-bm25 rapidfuzz rich
"""
import json
import sys
from pathlib import Path

# Windows: ensure UTF-8 for piped output (avoids Rich safe_box/box-drawing fallback bug)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_blocks():
    index_path = Path(__file__).parent.parent / "blocks" / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    all_blocks = data.get("blocks", []) + data.get("patterns", [])
    return [b for b in all_blocks if not b.get("internal")]


# -- Calibrated similarity thresholds ----------------------------------------
# MATCH_THRESHOLD -- normalised BM25 score floor for a confident positive result.
#   Blocks at or above this score are returned as results[]. Below it, they are
#   candidates for similar_blocks[] only (gap path).
#
# SIMILAR_FLOOR -- minimum score for a block to appear in similar_blocks[].
#   Blocks below this floor are noise -- suppress entirely rather than surface as partials.
MATCH_THRESHOLD = 0.947
SIMILAR_FLOOR = 0.578


def score_words(block, query_words):
    """Simple word-overlap score for connection ranking and fallback."""
    haystack = f"{block.get('topic', '')} {block.get('summary', '')}".lower()
    if not query_words:
        return 0
    return sum(1 for w in query_words if w in haystack) / len(query_words)


def get_related(primary_results, all_blocks, query_words, bm25_scores=None, cap=3):
    """1-hop graph traversal + proximity fallback for 'You should also know'.

    bm25_scores: dict of {file: normalised_bm25_score} for all blocks, returned by
    query_blocks(). When provided, the fallback filter uses SIMILAR_FLOOR against
    BM25 scores -- the same scale the threshold was calibrated on. Without it (fuzzy
    path), word-overlap is used with no floor, since score_words() is a different scale.
    """
    primary_files = {r[0]["file"] for r in primary_results}

    # Collect connection targets not in primary results, scored against the query
    candidates = {}
    for block, _ in primary_results:
        for conn in block.get("connections", []):
            if conn not in primary_files:
                candidate = next((b for b in all_blocks if b["file"] == conn), None)
                if candidate:
                    s = score_words(candidate, query_words)
                    candidates[conn] = max(candidates.get(conn, 0), s)

    related = sorted(candidates.items(), key=lambda x: -x[1])[:cap]

    # Fallback: next-highest-scoring blocks when connections are sparse.
    if len(related) < cap:
        seen = primary_files | {f for f, _ in related}
        if bm25_scores:
            fallback = sorted(
                [(f, s) for f, s in bm25_scores.items()
                 if f not in seen and s >= SIMILAR_FLOOR],
                key=lambda x: -x[1],
            )[: cap - len(related)]
        else:
            fallback = sorted(
                [(b["file"], score_words(b, query_words)) for b in all_blocks
                 if b["file"] not in seen and score_words(b, query_words) > 0],
                key=lambda x: -x[1],
            )[: cap - len(related)]
        related += fallback

    return [
        b for f, _ in related
        if (b := next((b for b in all_blocks if b["file"] == f), None))
    ]


def query_blocks(query: str, blocks: list, top_n: int = 3):
    """Score blocks against query and return (results, similar, bm25_scores, method).

    results      -- blocks with normalised BM25 score >= MATCH_THRESHOLD (confident matches)
    similar      -- blocks with SIMILAR_FLOOR <= score < MATCH_THRESHOLD (partial matches,
                   surfaced in gap responses as similar_blocks[])
    bm25_scores  -- dict of {file: normalised_score} for all blocks; passed to get_related()
                   so the SIMILAR_FLOOR filter operates on the same scale it was calibrated on
    method       -- 'bm25' or 'fuzzy'
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        print("Missing dependency: pip install rank-bm25", file=sys.stderr)
        sys.exit(1)

    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        print("Missing dependency: pip install rapidfuzz", file=sys.stderr)
        sys.exit(1)

    # Weight topic 2x by repeating it; summary provides depth
    corpus = [
        f"{b.get('topic', '')} {b.get('topic', '')} {b.get('summary', '')}".lower()
        for b in blocks
    ]
    tokenized = [text.split() for text in corpus]
    bm25 = BM25Okapi(tokenized)

    scores = bm25.get_scores(query.lower().split())
    max_score = float(scores.max()) if len(scores) > 0 else 0.0

    if max_score > 0.3:
        # Normalised scores for every block
        bm25_scores = {
            blocks[i]["file"]: round(float(scores[i] / max_score), 2)
            for i in range(len(blocks))
        }

        # Sort all blocks by score descending; partition by MATCH_THRESHOLD
        ranked = sorted(
            [(blocks[i], round(float(scores[i] / max_score), 2)) for i in range(len(blocks)) if scores[i] > 0],
            key=lambda x: -x[1],
        )
        results = [(b, s) for b, s in ranked if s >= MATCH_THRESHOLD][:top_n]
        similar = [(b, s) for b, s in ranked if SIMILAR_FLOOR <= s < MATCH_THRESHOLD][:top_n]
        return results, similar, bm25_scores, "bm25"

    # Fuzzy fallback -- token_set_ratio not partial_ratio
    targets = {
        i: f"{b.get('topic', '')} {b.get('summary', '')}"
        for i, b in enumerate(blocks)
    }
    fuzzy_results = process.extract(
        query, targets,
        scorer=fuzz.token_set_ratio,
        limit=top_n,
        score_cutoff=40,
    )
    return [
        (blocks[idx], round(score / 100.0, 2))
        for _, score, idx in fuzzy_results
    ], [], {}, "fuzzy"


def render_results(query, results, related, method, console):
    from rich.text import Text

    console.print()
    header = Text()
    header.append(f"  {query}", style="bold")
    header.append(f"  [{method}]", style="dim")
    console.print(header)
    console.print()

    for block, _score in results:
        confidence = block.get("confidence", "")
        staleness = block.get("staleness_risk", "")
        theory_delta = block.get("theory_delta", "")
        env_scope = block.get("environment_scope", "")
        summary = block.get("summary", "")

        # Confidence badge colour
        if confidence in ("validated", "verified", "empirical"):
            badge_style = "bold green"
        elif confidence in ("community-verified",):
            badge_style = "bold cyan"
        elif confidence in ("draft", "theoretical", "community-draft"):
            badge_style = "dim yellow"
        else:
            badge_style = "dim"

        staleness_str = ""
        if staleness == "high":
            staleness_str = " -- high staleness"
        elif staleness == "medium":
            staleness_str = " -- medium staleness"

        badge_text = f"[{confidence or 'unrated'}{staleness_str}]" if confidence or staleness_str else ""

        # Topic + badge
        title = Text()
        title.append(block.get("topic", block["file"]), style="bold")
        if badge_text:
            title.append("  ")
            title.append(badge_text, style=badge_style)
        console.print(title)

        # Environment scope
        if env_scope:
            console.print(Text(f"  {env_scope}", style="dim"))

        # Summary
        if summary:
            display = summary[:200] + "..." if len(summary) > 200 else summary
            console.print(f"  {display}")

        # Theory delta -- the key finding, flagged visually
        if theory_delta:
            console.print(Text(f"  !  {theory_delta}", style="bold yellow"))

        console.print()

    # You should also know
    if related:
        console.print(Text("  You should also know:", style="dim bold"))
        for r in related:
            line = Text()
            line.append("  ->  ", style="dim")
            line.append(r.get("topic", r["file"]))
            console.print(line)
            console.print(Text(f"       blocks/{r['file']}", style="dim"))
        console.print()


def render_gap(query, similar, console):
    """Render gap response. similar: list of (block, score) partial matches above SIMILAR_FLOOR."""
    from rich.text import Text

    console.print()
    console.print(Text(f'  No confident match for "{query}"', style="bold"))
    console.print()
    console.print(
        Text("  This topic is not yet covered. Consider adding a block for it.", style="dim")
    )

    if similar:
        console.print()
        console.print(Text("  Partial matches (below confidence threshold):", style="dim"))
        for block, score in similar:
            line = Text()
            line.append(f"  ~  [{score:.2f}]  ", style="dim")
            line.append(block.get("topic", block["file"]), style="dim")
            console.print(line)

    console.print()


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/query.py "your question" [--json]')
        sys.exit(1)

    json_output = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    query = " ".join(args)

    all_blocks = load_blocks()
    results, similar, bm25_scores, method = query_blocks(query, all_blocks)

    if json_output:
        if not results:
            print(json.dumps({
                "query": query,
                "results": [],
                "gap_detected": True,
                "similar_blocks": [
                    {"file": b["file"], "topic": b.get("topic", ""), "summary": b.get("summary", ""), "score": s}
                    for b, s in similar
                ],
                "count": 0,
            }))
        else:
            query_words = query.lower().split()
            related = get_related(results, all_blocks, query_words, bm25_scores)
            output = {
                "query": query,
                "results": [
                    {
                        "file": b["file"],
                        "topic": b.get("topic", ""),
                        "summary": b.get("summary", ""),
                        "theory_delta": b.get("theory_delta") or None,
                        "confidence": b.get("confidence") or None,
                        "staleness_risk": b.get("staleness_risk") or None,
                        "environment_scope": b.get("environment_scope") or None,
                        "score": score,
                    }
                    for b, score in results
                ],
                "related_blocks": [
                    {"file": r["file"], "topic": r.get("topic", ""), "summary": r.get("summary", "")}
                    for r in related
                ],
                "gap_detected": False,
                "count": len(results),
            }
            print(json.dumps(output, indent=2))
        return

    try:
        from rich.console import Console
        console = Console(highlight=False)
    except ImportError:
        # Plain-text fallback if rich not installed
        if not results:
            print(f"\nNo confident match for: {query}")
            if similar:
                print("Partial matches:")
                for block, score in similar:
                    print(f"  [{score:.2f}]  {block.get('topic', block['file'])}")
            print("Gap -- consider adding a block for this topic.")
        else:
            print(f"\nQuery: {query}  [{method}]\n")
            for block, score in results:
                print(f"  {score}  {block['file']}")
                print(f"       {block.get('topic', '')}")
                if block.get("theory_delta"):
                    print(f"  !  {block['theory_delta']}")
                print()
        return

    if not results:
        render_gap(query, similar, console)
    else:
        query_words = query.lower().split()
        related = get_related(results, all_blocks, query_words, bm25_scores)
        render_results(query, results, related, method, console)


if __name__ == "__main__":
    main()
