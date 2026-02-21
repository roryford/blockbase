# Blockbase

A structured knowledge base format with epistemological frontmatter, queryable via MCP.

Every block is a Markdown file that captures not just *what* you know, but *how confident* you are, *how quickly* it goes stale, and *where reality diverged from documentation*. Fork this repo, add your own blocks, and query them locally or via a Cloudflare Worker.

## Quickstart

```bash
# 1. Fork this repo and clone it
git clone https://github.com/YOUR_USERNAME/blockbase.git
cd blockbase

# 2. Install Python dependencies
pip install pyyaml rank-bm25 rapidfuzz rich

# 3. Add a block
cp blocks/example-block.md blocks/my-topic.md
# Edit blocks/my-topic.md with your findings

# 4. Validate and index
python scripts/validate_blocks.py blocks/my-topic.md
python scripts/generate_index.py

# 5. Query locally
python scripts/query.py "my topic"
```

## Deploy (optional)

The included Cloudflare Worker serves your blockbase as an MCP endpoint and REST API.

```bash
# Configure worker/wrangler.toml with your repo name
python scripts/generate_index.py
python scripts/bundle_worker.py
cd worker && npx wrangler deploy
```

## What Makes This Different

- **`theory_delta`** -- captures where observed behaviour diverged from docs. The gap between README and reality is exactly the knowledge worth preserving.
- **Epistemological frontmatter** -- every block declares its `confidence` level, `staleness_risk`, and specific `claims`. Not all knowledge is equal.
- **MCP-native** -- the Worker speaks MCP (Model Context Protocol), so AI agents can query your knowledge base directly.
- **Fork-and-diverge** -- this is a template, not a library. Your blockbase is yours. Customize the schema, add fields, change the worker.

## Schema

See [docs/SCHEMA.md](docs/SCHEMA.md) for the full frontmatter field reference.

## Dependencies

- Python 3.8+ with `pyyaml` (required)
- `rank-bm25`, `rapidfuzz`, `rich` (for local query -- `pip install rank-bm25 rapidfuzz rich`)
- Node.js + Wrangler (for Worker deployment only)

## License

MIT
