# Vibe coding — dual capture & business loops (ACP-9)

How to **observe** and **govern** coding-agent traffic (Claude Code first; Cursor/Codex later) in TokenSaver without turning the gateway into an IDE.

Product plan (platform repo): `docs/PLAN-VIBE-CODING-DEVELOPER-SPACE.md`.

## Two capture paths

| Path | Command | What it does |
|------|---------|--------------|
| **A — Route (pipeline)** | `tokensaver route claude --launch` | Claude talks to `ANTHROPIC_BASE_URL` → TokenSaver `/anthropic`. Policies enforce (catalog, PII, **`agentic_loop`** when headers present). |
| **B — Egress (MITM)** | `tokensaver-egress serve` + `claude` | Transparent capture of HTTPS LLM hosts → `egress_audit` → Flux IA / graph. Soft precheck if `TOKENSAVER_LOOP_ID` (from Claude MCP stamp). |

**Lab / Pro ideal:** same API key + same `loop_id` on A and/or B → one BusinessLoop in the console graph (`mode=loops`).

```text
IDE / Claude
   ├─ A) route → /anthropic  (enforce)
   └─ B) HTTPS_PROXY → egress (observe)
              │
              ▼
     Flux IA · Boucles · Cost Management
```

## When is it a Boucle?

| Situation | Entity | Graph layer |
|-----------|--------|-------------|
| Exploratory chat, no stop condition | Flows (+ maybe Tâche) | Complet / Tâches |
| Goal / max turns / schedule / MCP `tokensaver_loop_*` | **BusinessLoop** | **Boucles** |
| Repo attribution (git / catalog) | `project_*` attrs | **Projets** |

**Never** invent a loop from timestamps alone (SPEC-ACP-9).

## Start a governable loop

### Path A — Claude auto (preferred)

Skills **`tokensaver-agentic-loops`** + **`tokensaver-close-loop`** call MCP
`tokensaver_loop_start` / `tokensaver_loop_end` — the user does **not** run
`tokensaver loop start|end` in a terminal.

`tokensaver_loop_start` also writes `~/.tokensaver-egress/current-loop.env`; a
running `tokensaver-egress serve` **hot-reloads** that file so captures attach
without `serve --loop` or a shell export.

Reinstall after upgrade: `tokensaver-egress install-skills --force` (or
`tokensaver route claude`).

### Path B — Egress observe (no CLI loop)

```bash
tokensaver login
# Pro+: enable governance policy kind agentic_loop in the console

# Terminal A — observe only (do not use --loop; Claude MCP stamps the Boucle)
tokensaver-egress serve

# Terminal B — Claude; skills open/close the Boucle via MCP
claude
```

Open the graph: console → **Boucles** (or URL from status when using scripts).

### Scripts / emergency only

`tokensaver loop start|end|status` remains for labs and automation
(`examples/05-vibe-loop-lab.sh`). Humans and Claude should not rely on it for
day-to-day vibe coding.

## MCP (agents)

Lifecycle tools (used by skills, not by the human typing CLI):

- `tokensaver_loop_start` / `_iteration` / `_end` / `_precheck` / `_get`

Pass `loop_id` into subsequent tool/LLM calls when headers are available; egress
stamps from `current-loop.env` (MCP) or `TOKENSAVER_LOOP_ID` when `serve --loop`
was used.

## Clients (agnostic labels)

| Client | Route | `X-Tokensaver-Client` |
|--------|-------|------------------------|
| Claude Code | `tokensaver route claude` | `claude-code/1.0` (MCP gateway) |
| Cursor | `tokensaver route cursor` | `cursor/1.0` |
| Codex / OpenAI-shaped | `tokensaver route codex` / `proxy` | set header when the client allows; else egress + MCP stamp |

Same console hub and Boucles graph for all — filter by client/agent in Flux IA when present.

## Project stamp (git)

CLI `tokensaver loop start` (scripts) attaches `attrs.project_source=cli_git` and a stable `project_external_id` from `git remote get-url origin` (fallback: cwd basename). Used later by Espace développeur / calque Projets.

## Console (cible)

- **Espace développeur** (`/developer`) — hub: projects, loops, alerts, deep-links (not a second Cost Management).
- **Boucles** — approve / cancel / isolate.
- **Cost Management** — money; deep-link from the hub.
- **ACP-8** — on loop end, stop patterns write to the context graph when org write-back is enabled (Enterprise). Toggle: Settings → Organization → Context graph.

## Lab script

```bash
./examples/05-vibe-loop-lab.sh
```

Creates a loop, optional curl probe with headers, prints console URLs.

## Related docs

- [claude-code.md](claude-code.md) — `route claude`
- Platform: [RUNBOOK-EGRESS-ACP-4.md](../../../docs/RUNBOOK-EGRESS-ACP-4.md) (monorepo) / PyPI egress README
- [SPEC-ACP-9](../../../docs/SPEC-ACP-9-BUSINESS-AGENTIC-LOOPS.md) (monorepo)
