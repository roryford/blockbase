# Block Schema Reference

Every block is a Markdown file with YAML frontmatter. The frontmatter carries epistemological metadata -- not just what the block says, but how confident you should be in it.

## Frontmatter Fields

### Required

| Field | Type | Allowed Values | Purpose |
|-------|------|---------------|---------|
| `confidence` | string | `empirical`, `validated`, `secondary-research`, `inferred`, `medium`, `theoretical`, `draft`, `mixed`, `verified` | How confident you should be in this block's claims. `empirical`/`validated` blocks have been tested firsthand. `theoretical`/`draft` blocks are informed guesses. |

### Required for High-Confidence Blocks

| Field | Type | Allowed Values | Purpose |
|-------|------|---------------|---------|
| `staleness_risk` | string | `low`, `medium`, `high` | How quickly this block's claims might become outdated. `high` = check every 2 weeks. `medium` = check every 2 months. `low` = stable knowledge. |

### Recommended

| Field | Type | Purpose |
|-------|------|---------|
| `knowledge_type` | string (`validated`, `observed`, `theoretical`) | Classification of how this knowledge was obtained. |
| `claims` | list of strings | Specific, falsifiable claims this block makes. The atomic units of knowledge. Each claim should be testable. |
| `theory_delta` | string | Where observed behaviour diverged from documentation or expectations. This is the unique value of a blockbase -- capturing the gap between "what docs say" and "what actually happens". |
| `environment_scope` | string | What environment this was tested in (OS, versions, dates). Claims may not hold in other environments. |

### Optional

| Field | Type | Purpose |
|-------|------|---------|
| `categories` | list of strings | Topic categories for filtering (e.g. `["security", "mcp"]`). |
| `connected_blocks` | list of strings | Filenames of related blocks (e.g. `["other-block.md"]`). Auto-derived by `generate_index.py` from cross-references, but can be set manually. |
| `date` | string (ISO date) | When this block was researched. Can also be set in the body as `*Researched: YYYY-MM-DD*`. |
| `internal` | boolean | If `true`, block is excluded from user-facing query results but still appears in `index.json`. Use for implementation/infrastructure blocks. |

## Validation

Run `python scripts/validate_blocks.py blocks/your-block.md` to check format compliance.

The CI format gate (`.github/workflows/format-gate.yml`) runs this automatically on PRs that modify blocks.

## Block Body Structure

After the frontmatter, blocks follow a loose convention:

```markdown
# Block Title

*Researched: YYYY-MM-DD*

Opening paragraph summarizing the key finding (extracted as `summary` in the index).

## Key Findings
...

## What This Means for Builders
...
```

The first H1 becomes the `topic` in the index. The first body paragraph becomes the `summary`. Everything else is free-form.
