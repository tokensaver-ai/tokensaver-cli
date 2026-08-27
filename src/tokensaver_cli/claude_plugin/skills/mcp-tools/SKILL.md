---
name: tokensaver-mcp-tools
description: >-
  TokenSaver MCP tools reference for Claude Code — when to call tokensaver_* tools,
  quotas, runs, cache, RAG, governance, and Agent Registry. Use when the user asks
  for MCP tools, quotas, last run, cache, or platform data.
---

# TokenSaver MCP tools

MCP server: **`tokensaver-route-tools`** (HTTP). Auth: same Bearer as routing (session JWT or `TOKENSAVER_API_KEY`).

## Response rules

1. **ASCII dashboards** from quota/overview tools → paste **verbatim**, do not summarize into a table unless asked.
2. **Last run / run detail** → `tokensaver_get_last_run_detail` or `tokensaver_get_monitoring_run` once, paste ASCII.
3. **Model pick** → `tokensaver_list_models` before suggesting ids.
4. Respect **effective modules** on the key (cache/RAG/PII may be off via governance).

## Tool groups

### Chat & models

| Tool | Use when |
|------|----------|
| `tokensaver_chat` | Governed LLM Q&A (pipeline inside) |
| `tokensaver_list_models` | Available models for this key/plan |
| `tokensaver_create_chat` / `tokensaver_chat_in_session` | Multi-turn sessions |

### Quotas & cost

| Tool | Use when |
|------|----------|
| `tokensaver_get_api_key_overview` | Full key dashboard (primary) |
| `tokensaver_get_quota_usage` | Quotas + usage ASCII |
| `tokensaver_get_consumption` | Today/month consumption |
| `tokensaver_get_cost_breakdown` | Cost by model |
| `tokensaver_check_quota_alerts` | Near limits |

### Runs & observability (real-time control plane)

**Every Claude message routed through TokenSaver appears live in Flux IA** — pipeline steps, tokens, cost, MCP calls. Proactively suggest opening the console when users ask about runs, cost, or « what happened ».

| Tool | Use when |
|------|----------|
| `tokensaver_get_last_run_detail` | « Dernier run » / last pipeline run (paste ASCII) |
| `tokensaver_list_runs` | Recent runs list |
| `tokensaver_get_monitoring_run` | Step-by-step run (need request_id) |
| `tokensaver_open_run_console` | Open run in browser (real-time Flux IA) |
| `tokensaver_get_execution_trace` | Trace by execution_trace_id |

CLI: `tokensaver flows --open` opens Flux IA in the browser while Claude is working.

### Cache

| Tool | Use when |
|------|----------|
| `tokensaver_cache_stats` | Stats overview |
| `tokensaver_list_cache_entries` | Inspect entries |
| `tokensaver_cache_invalidate` | Wrong cached answer for one prompt |
| `tokensaver_cache_feedback` | Thumbs down + ban |

Do **not** use `tokensaver_cache_purge` to « disable » cache — use governance policies.

### Agent Registry / zero-trust

| Tool | Use when |
|------|----------|
| `tokensaver_list_catalog_assets` | List models/assets |
| `tokensaver_approve_catalog_asset` | Unblock quarantined model (`ref=provider/model`) |
| `tokensaver_set_catalog_asset_status` | Admin status changes |

CLI equivalent: `tokensaver approve`, `tokensaver catalog`.

### Governance & security

| Tool | Use when |
|------|----------|
| `tokensaver_list_governance_policies` | Policies on key |
| `tokensaver_security_summary` | Security overview |
| `tokensaver_list_security_events` | Recent events |

### RAG (if enabled for key)

| Tool | Use when |
|------|----------|
| `tokensaver_search_rag` | Search documents |
| `tokensaver_upload_rag_document` | Ingest document |

If RAG is disabled for the key, use `tokensaver_chat` without assuming RAG context.

## Fallback when MCP fails

```bash
tokensaver whoami
tokensaver status
tokensaver doctor --claude
```

If chat model returns 403, run **`tokensaver approve --current`** in the user's terminal.
