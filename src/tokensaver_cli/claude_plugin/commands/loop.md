---
description: Start / tick / end / status a TokenSaver BusinessLoop (ACP-9 vibe coding governance)
argument-hint: "[start|tick|end|status] [--kind goal_based] [--goal …] [--max-turns N]"
---

# Business loop — do this exactly

When the user wants to **govern** a coding goal / iterative session (not casual chat):

## Step 1 — prefer MCP

On server **`tokensaver-route-tools`**, call in order:

1. `tokensaver_loop_start` (kind `goal_based` unless user says otherwise; include goal + max_turns)
2. Remember `loop_id`
3. After meaningful progress: `tokensaver_loop_iteration`
4. When done: `tokensaver_loop_end` with a `stop_reason`

If MCP is unavailable, Bash:

```bash
tokensaver loop start --kind goal_based --goal "USER_GOAL" --max-turns 8
eval "$(tokensaver loop env)"
```

Paste CLI stdout **verbatim** when using Bash.

## Step 2 — tell the user

- Open **Espace développeur** or graphe **Boucles** to Isoler / Approuver / Annuler  
- Egress path: keep `TOKENSAVER_LOOP_ID` exported; optional `TOKENSAVER_LOOP_PRECHECK=1`

## Hard rules

- Do **not** create a loop for vague exploration with no stop condition  
- Do **not** invent tool names  
- Follow skill **`tokensaver-agentic-loops`** for kinds and stop reasons
