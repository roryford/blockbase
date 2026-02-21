/**
 * Blockbase Cloudflare Worker -- minimal knowledge base query server
 *
 * REST endpoints:
 *   GET  /health
 *   GET  /.well-known/agent-card.json  -- A2A Agent Card
 *   GET  /blocks?topic=X&category=Y&since=2025-01-01
 *   GET  /blocks/:file              -- fetch a specific block by filename
 *
 * MCP endpoint (Streamable HTTP, stateless):
 *   POST /mcp  -- JSON-RPC 2.0, tools: query, get_block, list_blocks
 *
 * index.json is bundled at deploy time (run scripts/bundle_worker.py first).
 * Block content is fetched live from raw.githubusercontent.com.
 *
 * Environment variables (set in wrangler.toml [vars]):
 *   BLOCKBASE_NAME  -- display name for the knowledge base
 *   GITHUB_REPO     -- "username/repo-name" for raw content fetching
 */

import INDEX_DATA from "./blocks-index.json";

// --- Module-level constants ---
const GAP_THRESHOLD = 0.20;

function getConfig(env) {
  const name = env.BLOCKBASE_NAME || "Blockbase";
  const repo = env.GITHUB_REPO || "username/repo-name";
  const workerUrl = env.WORKER_URL || "https://localhost:8787";
  return { name, repo, workerUrl };
}

function buildAgentCard(env) {
  const { name, repo, workerUrl } = getConfig(env);
  return {
    name,
    description: `${name} -- a structured knowledge base with epistemological frontmatter. Query for empirical findings, theory deltas, and cross-block patterns.`,
    url: workerUrl,
    provider: {
      organization: name,
      url: `https://github.com/${repo}`,
    },
    version: "1.0.0",
    documentationUrl: `https://github.com/${repo}`,
    authentication: {
      schemes: [],
      credentials: null,
    },
    capabilities: {
      streaming: false,
      pushNotifications: false,
      stateTransitionHistory: false,
    },
    defaultInputModes: ["text/plain"],
    defaultOutputModes: ["text/plain"],
    skills: [
      {
        id: "query",
        name: `Query ${name}`,
        description: `Search the ${name} knowledge base. Returns matching blocks with summaries, confidence levels, and theory_delta where observed behaviour diverged from docs.`,
        tags: ["discovery", "knowledge"],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
      {
        id: "get_block",
        name: "Get Block Content",
        description: "Fetch the full markdown content of a specific knowledge block by filename.",
        tags: ["knowledge", "blocks"],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
      {
        id: "list_blocks",
        name: "List Blocks",
        description: `List all topics in the ${name} knowledge base with filenames and confidence levels.`,
        tags: ["discovery", "index", "topics"],
        inputModes: ["text/plain"],
        outputModes: ["text/plain"],
      },
    ],
  };
}

function buildMcpTools(env) {
  const { name } = getConfig(env);
  return [
    {
      name: "query",
      description:
        `Search the ${name} knowledge base. ` +
        "Returns matching blocks with summaries, confidence levels, and theory_delta where observed behaviour diverged from docs. " +
        "Use list_blocks to browse all topics first. Use get_block for full content.",
      inputSchema: {
        type: "object",
        properties: {
          topic: {
            type: "string",
            description: "Keyword to search in block topics and summaries",
          },
          category: {
            type: "string",
            description: "Filter by category",
          },
          since: {
            type: "string",
            description: "ISO date -- only return blocks researched after this date (e.g. '2025-01-01')",
          },
          kind: {
            type: "string",
            enum: ["blocks", "patterns"],
            description: "Limit to blocks or patterns only. Omit for both.",
          },
          limit: {
            type: "number",
            description: "Max results to return (default 10)",
          },
        },
      },
    },
    {
      name: "get_block",
      description: "Fetch the full markdown content of a specific block or pattern by filename.",
      inputSchema: {
        type: "object",
        properties: {
          filename: {
            type: "string",
            description:
              "Block filename (e.g. 'example-block.md'). " +
              "Use query first to find the filename.",
          },
        },
        required: ["filename"],
      },
    },
    {
      name: "list_blocks",
      description:
        `List all topics in the ${name} knowledge base with filenames and confidence levels. ` +
        "Use this to browse what's covered before querying, or to find the exact filename for get_block.",
      inputSchema: {
        type: "object",
        properties: {
          kind: {
            type: "string",
            enum: ["blocks", "patterns"],
            description: "Limit to blocks or patterns only. Omit for both.",
          },
        },
      },
    },
  ];
}

// --- Main fetch handler ---

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return corsResponse("", 204);
    }

    if (url.pathname === "/health") {
      return corsResponse(JSON.stringify({ status: "ok" }), 200, "application/json");
    }

    // MCP endpoint
    if (url.pathname === "/mcp") {
      if (request.method === "POST") {
        return handleMcp(request, env);
      }
      return corsResponse(
        JSON.stringify({ error: "Use POST for MCP JSON-RPC requests" }),
        405,
        "application/json"
      );
    }

    // A2A Agent Card
    if (url.pathname === "/.well-known/agent-card.json" || url.pathname === "/.well-known/agent.json") {
      return corsResponse(JSON.stringify(buildAgentCard(env), null, 2), 200, "application/json");
    }

    // REST block endpoints
    if (url.pathname === "/blocks" || url.pathname === "/") {
      return handleList(url);
    }

    const fileMatch = url.pathname.match(/^\/blocks\/(.+\.md)$/);
    if (fileMatch) {
      return handleFile(fileMatch[1], env);
    }

    return corsResponse("Not found", 404);
  },
};

// --- MCP handler ---

async function handleMcp(request, env) {
  const { name } = getConfig(env);

  let body;
  try {
    body = await request.json();
  } catch {
    return mcpError(null, -32700, "Parse error");
  }

  const { jsonrpc, id, method, params } = body;

  if (jsonrpc !== "2.0") {
    return mcpError(id ?? null, -32600, "Invalid Request: jsonrpc must be '2.0'");
  }

  switch (method) {
    case "initialize":
      return mcpResult(id, {
        protocolVersion: "2024-11-05",
        serverInfo: { name: name.toLowerCase().replace(/\s+/g, "-"), version: "1.0.0" },
        capabilities: { tools: {} },
      });

    case "notifications/initialized":
      return new Response(null, { status: 204 });

    case "tools/list":
      return mcpResult(id, { tools: buildMcpTools(env) });

    case "tools/call": {
      const { name: toolName, arguments: args } = params ?? {};
      if (toolName === "query") return mcpToolQuery(id, args ?? {}, env);
      if (toolName === "get_block") return mcpToolGetBlock(id, args ?? {}, env);
      if (toolName === "list_blocks") return mcpToolListBlocks(id, args ?? {});
      return mcpError(id, -32602, `Unknown tool: ${toolName}`);
    }

    default:
      return mcpError(id ?? null, -32601, `Method not found: ${method}`);
  }
}

// --- Scoring ---

// Score an index entry against a list of query words.
// Fields are weighted: topic (3x) > summary (2x) > claims (1x) > theory_delta (1x) > connections (0.5x).
// Returns a normalised score 0-1 relative to the maximum possible per-word hit.
function scoreEntry(entry, queryWords) {
  const fields = [
    { text: entry.topic ?? "", weight: 3 },
    { text: entry.summary ?? "", weight: 2 },
    { text: (entry.claims ?? []).join(" "), weight: 1 },
    { text: entry.theory_delta ?? "", weight: 1 },
    { text: (entry.connections ?? []).join(" "), weight: 0.5 },
  ];
  let score = 0;
  const maxPerWord = fields.reduce((s, f) => s + f.weight, 0);
  for (const word of queryWords) {
    for (const { text, weight } of fields) {
      if (text.toLowerCase().includes(word)) score += weight;
    }
  }
  return score / (maxPerWord * queryWords.length);
}

// 1-hop graph traversal + proximity fallback for related blocks.
function getRelated(primaryResults, pool, queryWords, cap = 3) {
  const primaryFiles = new Set(primaryResults.map(r => r.file));

  const candidates = new Map();
  for (const r of primaryResults) {
    for (const conn of (r.connections ?? [])) {
      if (!primaryFiles.has(conn)) {
        const block = pool.find(b => b.file === conn);
        if (block) {
          const s = scoreEntry(block, queryWords);
          candidates.set(conn, Math.max(candidates.get(conn) ?? 0, s));
        }
      }
    }
  }

  let related = [...candidates.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, cap)
    .map(([file]) => pool.find(b => b.file === file))
    .filter(Boolean);

  // Proximity fallback when connections are sparse
  if (related.length < cap) {
    const seen = new Set([...primaryFiles, ...related.map(r => r.file)]);
    const fallback = pool
      .filter(b => !seen.has(b.file))
      .map(b => ({ b, score: scoreEntry(b, queryWords) }))
      .filter(r => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, cap - related.length)
      .map(r => r.b);
    related = [...related, ...fallback];
  }

  return related;
}

// --- MCP tool handlers ---

function mcpToolQuery(id, args, env) {
  const { name } = getConfig(env);
  const { topic, category, since, kind, limit = 10 } = args;
  const categoryLower = category?.toLowerCase();

  const index = INDEX_DATA;
  let pool = [];
  if (!kind || kind === "blocks") pool.push(...index.blocks);
  if (!kind || kind === "patterns") pool.push(...index.patterns);
  pool = pool.filter(e => !e.internal);

  // Pre-filter on category and since
  let filtered = pool.filter((entry) => {
    if (categoryLower) {
      if (!entry.categories?.some((c) => c.toLowerCase().includes(categoryLower))) return false;
    }
    if (since && entry.date && entry.date < since) return false;
    return true;
  });

  // Score + rank by topic query if provided
  let results;
  let queryWords = [];
  if (topic) {
    queryWords = topic.toLowerCase().split(/\s+/).filter(Boolean);
    results = filtered
      .map(entry => ({ entry, score: scoreEntry(entry, queryWords) }))
      .filter(r => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(r => r.entry);
  } else {
    results = filtered.slice(0, limit);
  }

  const topScore = topic && results.length > 0 ? scoreEntry(results[0], queryWords) : null;
  const gapDetected = results.length === 0 || (topic && topScore !== null && topScore < GAP_THRESHOLD);
  const nearMiss = gapDetected && results.length > 0 && topScore !== null && topScore > 0;

  // Related items (1-hop graph traversal + proximity fallback)
  const allPool = [...index.blocks, ...index.patterns].filter(e => !e.internal);
  const related = gapDetected ? [] : getRelated(results, allPool, queryWords);

  const visibleResults = gapDetected ? [] : results;

  // Staleness warning
  const today = Date.now();
  const staleFiles = visibleResults.filter(r => {
    if (!r.staleness_risk || !r.date) return false;
    const ageInDays = (today - new Date(r.date).getTime()) / 86_400_000;
    if (r.staleness_risk === "high") return ageInDays > 14;
    if (r.staleness_risk === "medium") return ageInDays > 60;
    return false;
  }).map(r => r.file);

  const responseData = {
    results: visibleResults.map(r => ({
      file: r.file,
      topic: r.topic,
      summary: r.summary,
      theory_delta: r.theory_delta ?? null,
      confidence: r.confidence ?? null,
      staleness_risk: r.staleness_risk ?? null,
      environment_scope: r.environment_scope ?? null,
    })),
    related_blocks: related.map(r => ({
      file: r.file,
      topic: r.topic,
      summary: r.summary,
    })),
    gap_detected: gapDetected,
    near_miss: nearMiss,
    top_score: topScore !== null ? Math.round(topScore * 100) / 100 : null,
    ...(staleFiles.length > 0 ? { staleness_warning: staleFiles } : {}),
    count: visibleResults.length,
    index_generated: index.generated,
    hint: gapDetected
      ? (nearMiss
          ? `Weak match (top_score=${Math.round(topScore * 100) / 100}, threshold=${GAP_THRESHOLD}). Try broader terms or call list_blocks to browse topics.`
          : `No blocks found. Call list_blocks to browse what's covered.`)
      : "Use get_block(filename) for full content.",
  };

  return mcpResult(id, { content: [{ type: "text", text: JSON.stringify(responseData, null, 2) }] });
}

async function mcpToolGetBlock(id, args, env) {
  const { filename } = args;
  if (!filename) {
    return mcpError(id, -32602, "filename is required");
  }
  // Allowlist: alphanumeric + hyphens/underscores only, must end in .md
  if (!/^[\w-]+\.md$/.test(filename)) {
    return mcpError(id, -32602, "Invalid filename: must be alphanumeric with hyphens, ending in .md");
  }

  const { repo } = getConfig(env);
  const rawBase = `https://raw.githubusercontent.com/${repo}/main/blocks/`;
  const patternBase = `https://raw.githubusercontent.com/${repo}/main/patterns/`;

  for (const base of [rawBase, patternBase]) {
    try {
      const res = await fetch(`${base}${filename}`);
      if (res.ok) {
        const text = await res.text();
        return mcpResult(id, { content: [{ type: "text", text }] });
      }
    } catch (_) {}
  }

  return mcpResult(id, {
    content: [{ type: "text", text: `Block not found: ${filename}` }],
    isError: true,
  });
}

function mcpToolListBlocks(id, args) {
  const { kind } = args ?? {};
  const index = INDEX_DATA;

  const blocks = (!kind || kind === "blocks")
    ? index.blocks
        .filter(b => !b.internal)
        .map(b => ({ file: b.file, topic: b.topic, confidence: b.confidence ?? null, date: b.date ?? null }))
    : [];

  const patterns = (!kind || kind === "patterns")
    ? index.patterns
        .filter(p => !p.internal)
        .map(p => ({ file: p.file, topic: p.topic, confidence: p.confidence ?? null, date: p.date ?? null }))
    : [];

  return mcpResult(id, {
    content: [{
      type: "text",
      text: JSON.stringify({
        blocks,
        patterns,
        total: blocks.length + patterns.length,
        hint: "Use get_block(filename) for full content. Use query(topic) to search by keyword.",
      }, null, 2),
    }],
  });
}

// --- REST handlers ---

function handleList(url) {
  const topic = url.searchParams.get("topic")?.toLowerCase();
  const category = url.searchParams.get("category")?.toLowerCase();
  const since = url.searchParams.get("since");
  const kind = url.searchParams.get("kind");

  const index = INDEX_DATA;
  let pool = [];
  if (!kind || kind === "blocks") pool.push(...index.blocks);
  if (!kind || kind === "patterns") pool.push(...index.patterns);

  const results = pool.filter((entry) => {
    if (topic) {
      const haystack = `${entry.topic} ${entry.summary}`.toLowerCase();
      if (!haystack.includes(topic)) return false;
    }
    if (category) {
      if (!entry.categories?.some((c) => c.toLowerCase().includes(category))) return false;
    }
    if (since && entry.date && entry.date < since) return false;
    return true;
  });

  return corsResponse(
    JSON.stringify({ generated: index.generated, query: { topic, category, since, kind }, count: results.length, results }, null, 2),
    200,
    "application/json"
  );
}

async function handleFile(filename, env) {
  const { repo } = getConfig(env);
  const rawBase = `https://raw.githubusercontent.com/${repo}/main/blocks/`;
  const patternBase = `https://raw.githubusercontent.com/${repo}/main/patterns/`;

  for (const base of [rawBase, patternBase]) {
    try {
      const res = await fetch(`${base}${filename}`);
      if (res.ok) {
        const text = await res.text();
        return corsResponse(text, 200, "text/markdown; charset=utf-8");
      }
    } catch (_) {}
  }

  return corsResponse("Block not found", 404);
}

// --- Utilities ---

function mcpResult(id, result) {
  return mcpJson({ jsonrpc: "2.0", id, result });
}

function mcpError(id, code, message) {
  return mcpJson({ jsonrpc: "2.0", id, error: { code, message } });
}

function mcpJson(body) {
  return new Response(JSON.stringify(body), {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

function corsResponse(body, status = 200, contentType = "text/plain") {
  return new Response(body, {
    status,
    headers: {
      "Content-Type": contentType,
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
