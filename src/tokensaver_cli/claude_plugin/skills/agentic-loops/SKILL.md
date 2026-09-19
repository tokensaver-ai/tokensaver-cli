---
name: tokensaver-agentic-loops
description: >-
  TokenSaver ACP-9 business loops for vibe coding — when the user sets a /goal,
  iterative coding task, or asks to govern a session, wrap work with
  tokensaver_loop_start / tick / end (or CLI tokensaver loop). Use for goals,
  max turns, budgets, Boucles graph, approve/cancel.
---

# TokenSaver — agentic loops (ACP-9)

TokenSaver **governs and traces** loops; it does **not** replace Claude’s `/goal` or `/schedule` orchestrator.

## When to wrap a BusinessLoop

| User intent | Action |
|-------------|--------|
| Explicit **goal** / stop condition / max turns | `tokensaver_loop_start` (`goal_based`) then work |
| Long iterative coding with a success criterion | same |
| « Gouverne cette session » / « ouvre une boucle » | start loop + tell user about Espace développeur / Boucles |
| Exploratory chat, no stop condition | **Do not** invent a loop |

Never invent `loop_kind` from timestamps. No loop ⇒ Flux IA / Tâches only.

## Preferred path (MCP)

Server: **`tokensaver-route-tools`**. Exact tool names:

1. **`tokensaver_loop_start`** — before iterative work  
   - `loop_kind`: `goal_based` (typical) | `turn_based` | `time_based` | `proactive` | `tool_linked` | `custom_sco`  
   - Pass goal expression + `max_turns` when known  
2. Keep `loop_id` from the result  
3. **`tokensaver_loop_iteration`** (or tick) at meaningful milestones  
4. **`tokensaver_loop_precheck`** before expensive turns if policy is active  
5. **`tokensaver_loop_end`** with `stop_reason` (`goal_met`, `work_complete`, `cancelled`, …)  
6. **`tokensaver_loop_get`** to inspect status

Also pass `loop_id` into subsequent `tokensaver_chat` / document `X-Tokensaver-Loop-Id` for egress.

## CLI fallback (Bash)

```bash
tokensaver loop start --kind goal_based --goal "<criterion>" --max-turns 8
eval "$(tokensaver loop env)"
# … coding work …
tokensaver loop tick
tokensaver loop end --reason goal_met
tokensaver loop status
```

With egress capture: keep `TOKENSAVER_LOOP_*` in the env of `tokensaver-egress serve` / `claude`, optionally `TOKENSAVER_LOOP_PRECHECK=1`.

## Tell the user (brief)

- Console → **Espace développeur** or graphe **Boucles** (`mode=loops&loopId=…`)  
- Approve / Cancel when status is `awaiting_approval`  
- Cost detail stays in **Cost Management** (hub is not a second ledger)

## Hard rules

- Do **not** invent MCP tool names (PascalCase / plugin-prefixed).  
- Do **not** claim a Boucle exists without `loop_id` / start success.  
- Policy `agentic_loop` may be Pro+ — if start fails with plan error, say so and continue ungoverened observation via Flux IA.
