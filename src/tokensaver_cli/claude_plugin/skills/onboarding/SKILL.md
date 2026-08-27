---
name: tokensaver-onboarding
description: >-
  TokenSaver onboarding for Claude Code — welcome users, explain routing, slash
  commands, MCP tools, models, quotas, and Flux IA. Use at session start, when
  the user says hello, asks how TokenSaver works, or needs setup help.
---

# TokenSaver onboarding (Claude Code)

You are running inside **Claude Code routed through TokenSaver**. Auth is a **session JWT** (same as the web console) — the backend maps it to the user's API key. **Never ask the user to paste a `ts_…` secret** unless they explicitly use CI env vars.

## When to use this skill

- First message in a routed session (greet + brief orientation)
- User asks *comment utiliser TokenSaver*, *what can you do*, *help*, *setup*
- User is blocked (403 model, quota, email not verified)
- User wants models, quotas, runs, or governance explained

**Language:** reply in the user's language (French if they write in French).

## Welcome message template

On the **first user message** of a session (or when they greet you), give a short friendly welcome like:

> **TokenSaver** route vos requêtes Claude via le plan de contrôle (gouvernance, quotas, Agent Registry).
>
> **Observabilité en temps réel :** chaque message et run IA exécuté dans Claude apparaît **en direct** dans le control plane TokenSaver (**Flux IA**) — étapes pipeline (cache, PII, LLM, MCP), tokens, coût. Ouvrez la console pendant que vous codez :
> - `/tokensaver-router:flows` ou `tokensaver flows --open`
> - MCP : `tokensaver_get_last_run_detail`, `tokensaver_open_run_console`
>
> **Modèle actif :** statusline en bas (`TokenSaver · routed · …`).
>
> **Pour commencer :**
> - `/tokensaver-router:help` — liste des commandes
> - `/tokensaver-router:models` puis `/tokensaver-router:use cheap|default|strong|provider/model`
> - `/tokensaver-router:whoami` — compte, plan, lien Flux IA
> - `/tokensaver-router:quota` — quotas (MCP)
>
> **Terminal** (si le modèle chat est bloqué) : `tokensaver whoami`, `tokensaver doctor --claude`, `tokensaver approve --current`.
>
> Comment puis-je vous aider ?

Adapt length to context; do not repeat on every turn.

## Core concepts (explain simply)

| Topic | What to tell the user |
|-------|----------------------|
| **Routing** | `ANTHROPIC_BASE_URL` → TokenSaver API; Bearer = session JWT |
| **Models** | Profiles `cheap` / `default` / `strong` depend on plan (Free = allowlist) |
| **Zero-trust** | Models must be **approved** in Agent Registry — use `/tokensaver-router:approve` or `tokensaver approve --current` |
| **Flux IA (temps réel)** | **Chaque run Claude** transite le pipeline TokenSaver et est visible **en direct** dans la console (Flux IA) : étapes, tokens, coût, MCP. `/tokensaver-router:flows`, `tokensaver flows --open`, ou MCP `tokensaver_open_run_console` |
| **Agentic graph** | Handoffs multi-agents tracés en temps réel — console → *Agentic graph* (même workspace) |
| **Quotas** | MCP `tokensaver_get_api_key_overview` or `tokensaver_get_quota_usage` — paste ASCII verbatim |
| **Login** | `tokensaver login` in terminal — JWT only, no key on disk |

## Slash commands (prefer over reinventing)

Load **`/tokensaver-router:help`** catalogue when the user asks for commands.

High-value paths:

1. **Not configured** → `/tokensaver-router:setup` (or `tokensaver login` + `tokensaver route claude`)
2. **Change model** → `/tokensaver-router:use <profile|model>`
3. **403 model** → `/tokensaver-router:approve` then retry
4. **Usage / cost** → `/tokensaver-router:quota`
5. **See live runs** → `/tokensaver-router:flows` or `tokensaver flows --open` (control plane updates as Claude works)
6. **Debug** → `/tokensaver-router:doctor`

## MCP tools skill

For MCP tool names and paste rules, load skill **`tokensaver-mcp-tools`**.

## Do not

- Invent API keys or ask users to create a second Free-plan key (quota 1/1)
- Rewrite MCP ASCII dashboards into prose — paste them as-is
- Run destructive cache ops (`tokensaver_cache_purge`) without explicit user request
