# Blockbase -- AI Agent Orientation

## What This Is

A blockbase is a structured knowledge base where each "block" is a Markdown file with epistemological frontmatter. Blocks capture empirical findings -- what actually works, not just what docs claim. The key differentiator is `theory_delta`: where observed behaviour diverged from documentation.

## Architecture

```
blocks/           -- knowledge blocks (one topic per file, YAML frontmatter)
blocks/index.json -- machine-readable index (regenerate: python scripts/generate_index.py)
patterns/         -- recurring patterns extracted from blocks
scripts/
  generate_index.py  -- sync blocks/index.json from block frontmatter
  validate_blocks.py -- validate block format (CI gate)
  query.py           -- local keyword search over index.json
  bundle_worker.py   -- copy index.json into worker for deploy
worker/           -- Cloudflare Worker (MCP + REST query interface)
docs/SCHEMA.md    -- frontmatter field reference
```

## How to Add a Block

1. Create `blocks/your-topic.md` with YAML frontmatter (see `docs/SCHEMA.md` for field reference)
2. Required frontmatter: `confidence` (empirical | validated | medium | theoretical | draft)
3. For empirical/validated blocks: `staleness_risk` is also required (low | medium | high)
4. Recommended: `claims` (list), `theory_delta` (string), `knowledge_type`, `environment_scope`
5. Run `python scripts/validate_blocks.py blocks/your-topic.md` to check format
6. Run `python scripts/generate_index.py` to update the index

## How to Query

Local: `python scripts/query.py "your question"` (requires: `pip install pyyaml rank-bm25 rapidfuzz rich`)

Via MCP: The worker exposes three MCP tools:
- `query` -- keyword search with scored results
- `get_block` -- fetch full block content by filename
- `list_blocks` -- browse all topics

## How to Deploy

```bash
python scripts/generate_index.py    # update index from blocks
python scripts/bundle_worker.py     # copy index into worker
cd worker && npx wrangler deploy    # deploy to Cloudflare
```

Configure `worker/wrangler.toml` with your `BLOCKBASE_NAME` and `GITHUB_REPO`.

## Key Concepts

- **theory_delta**: The gap between documentation and reality. This is what makes a blockbase valuable -- it captures tacit knowledge that docs don't.
- **confidence levels**: Not all knowledge is equal. `empirical` means tested firsthand. `theoretical` means reasoned but untested.
- **staleness_risk**: Knowledge decays. High-staleness blocks need re-checking every 2 weeks.
- **claims**: Specific, falsifiable statements. The atomic unit of blockbase knowledge.
