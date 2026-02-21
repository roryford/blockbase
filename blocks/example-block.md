---
knowledge_type: validated
confidence: empirical
staleness_risk: low
theory_delta: "Documentation claims X works out of the box -- in practice, requires manual configuration of Y before first use"
environment_scope: "Tested on macOS 14.3, Python 3.11, January 2025"
claims:
  - "Tool X requires manual Y configuration despite docs claiming automatic setup"
  - "Performance degrades above 1000 items without Z indexing"
  - "v2.0 API is backwards-compatible with v1.x despite changelog claiming breaking changes"
categories:
  - example
connected_blocks:
  - example-pattern.md
date: 2025-01-15
---

# Example Block -- Tool X Deep Dive

*Researched: 2025-01-15*

Tool X is a widely-used library for doing Y. This block captures what we learned by actually using it, not what the README claims.

## Key Findings

The documentation says setup is automatic. In practice, you need to manually configure Y before anything works. This is a common pattern -- tools optimise their README for first impressions, not first use.

## Performance

Below 1000 items, performance is acceptable. Above that threshold, you need Z indexing or queries take 3-5 seconds. The docs don't mention this cliff.

## API Compatibility

Despite the v2.0 changelog listing "breaking changes", the v1.x API still works unchanged. The breaking changes are in an optional module that most users don't import.

## What This Means for Builders

If you're evaluating Tool X: the setup friction is real but one-time. Once past it, the tool delivers on its promises. Budget 30 minutes for initial configuration, not the "5 minutes" the quickstart claims.
