---
knowledge_type: observed
confidence: medium
staleness_risk: low
theory_delta: "Pattern appears independently in 3+ unrelated tools -- likely fundamental, not coincidental"
claims:
  - "This pattern recurs across at least 3 independent implementations"
  - "Each implementation discovered it independently rather than copying from a common source"
  - "The pattern solves a structural constraint, not a preference"
categories:
  - example
  - patterns
connected_blocks:
  - example-block.md
date: 2025-01-15
---

# Example Pattern -- Convergent Design

*Observed: 2025-01-15*

When three or more independent tools solve the same problem the same way without copying each other, that's a pattern worth naming. This is convergent design -- structural constraints producing identical solutions.

## Evidence Table

| Tool | Implementation | Independent? | Date observed |
|------|---------------|-------------|---------------|
| Tool A | Uses bounded retry with exponential backoff | Yes (pre-dates others) | 2024-06 |
| Tool B | Same retry logic, different codebase | Yes (no shared deps) | 2024-09 |
| Tool C | Identical approach, third language | Yes (author unaware of A/B) | 2025-01 |

## Why This Matters

Convergent patterns are more reliable than prescribed patterns. They emerge from real constraints rather than theoretical best practices. When you see convergence, the pattern is load-bearing -- removing it will break things.

## Anti-pattern

Seeing two tools do something the same way is coincidence. Three is a pattern. One is an opinion. Don't elevate opinions to patterns.
