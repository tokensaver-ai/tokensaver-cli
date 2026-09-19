# Vibe coding — dual capture & business loops (ACP-9)

How to **observe** and **govern** coding-agent traffic (Claude Code first; Cursor/Codex later) in TokenSaver without turning the gateway into an IDE.

Product plan (platform repo): `docs/PLAN-VIBE-CODING-DEVELOPER-SPACE.md`.

## Two capture paths

| Path | Command | What it does |
|------|---------|--------------|
| **A — Route (pipeline)** | `tokensaver route claude --launch` | Claude talks to `ANTHROPIC_BASE_URL` → TokenSaver `/anthropic`. Policies enforce (catalog, PII, **`agentic_loop`** when headers present). |
| **B — Egress (MITM)** | `tokensaver-egress claude` | Transparent capture of HTTPS LLM hosts → `egress_audit` → Flux IA / graph. Soft precheck if `TOKENSAVER_LOOP_ID` + `TOKENSAVER_LOOP_PRECHECK=1`. |

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

## Start a governable loop (CLI)

```bash
tokensaver login
# Pro+: enable governance policy kind agentic_loop in the console

tokensaver loop start --kind goal_based --goal "tests green" --max-turns 5
# prints loop_id and shell exports:

eval "$(tokensaver loop start --kind goal_based --max-turns 5 --export)"
# → TOKENSAVER_LOOP_ID, TOKENSAVER_LOOP_KIND, TOKENSAVER_LOOP_ITERATION

# Path B — egress inherits env on the proxy process:
TOKENSAVER_LOOP_PRECHECK=1 tokensaver-egress serve   # terminal A
tokensaver-egress claude --no-start                  # terminal B (same env)

# Path A — send headers on LLM calls (curl / SDK / MCP):
#   X-Tokensaver-Loop-Id: $TOKENSAVER_LOOP_ID
#   X-Tokensaver-Loop-Kind: goal_based
#   X-Tokensaver-Loop-Iteration: 1
# Claude Code does not always forward custom headers; prefer MCP
# tokensaver_loop_start / _iteration / _end, or egress path B.

tokensaver loop tick          # bump iteration + event
tokensaver loop status        # ASCII detail
tokensaver loop end --reason goal_met
```

Open the graph: URL printed by `tokensaver loop status` (Boucles) or console → **Graphe d’exécution agentique** → mode **Boucles**.

## MCP (agents)

Same lifecycle without the CLI:

- `tokensaver_loop_start` / `_iteration` / `_end` / `_precheck` / `_get`

Pass `loop_id` into subsequent tool/LLM calls (`X-Tokensaver-Loop-Id` or chat metadata).

## Clients (agnostic labels)

| Client | Route | `X-Tokensaver-Client` |
|--------|-------|------------------------|
| Claude Code | `tokensaver route claude` | `claude-code/1.0` (MCP gateway) |
| Cursor | `tokensaver route cursor` | `cursor/1.0` |
| Codex / OpenAI-shaped | `tokensaver route codex` / `proxy` | set header when the client allows; else egress + `TOKENSAVER_LOOP_ID` |

Same console hub and Boucles graph for all — filter by client/agent in Flux IA when present.

## Project stamp (git)

`tokensaver loop start` attaches `attrs.project_source=cli_git` and a stable `project_external_id` from `git remote get-url origin` (fallback: cwd basename). Used later by Espace développeur / calque Projets.

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
