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

On session start (via `initialUserMessage`) **and** on the first user message / greeting,
your **first assistant reply** MUST be this welcome (adapt language; French by default):

> **Bienvenue sur TokenSaver**
>
> Vos requêtes Claude passent par le control plane (gouvernance, quotas, Agent Registry).
> **Chaque run IA** est visible **en temps réel** dans Flux IA.
>
> **Actions utiles :**
> 1. `/tokensaver-router:models` puis `/tokensaver-router:use …` — choisir un modèle
> 2. `/tokensaver-router:flows` ou `tokensaver flows --open` — voir les runs live
> 3. `/tokensaver-router:quota` — quotas / usage
> 4. `/tokensaver-router:whoami` — compte & plan
> 5. `/tokensaver-router:help` — toutes les commandes
>
> Dis-moi ce que tu veux faire (coder, changer de modèle, voir les coûts…).

Do **not** wait for the user to ask how TokenSaver works — lead with this guide once per session.

## Core concepts (explain simply)

| Topic | What to tell the user |
|-------|----------------------|
| **Routing** | `ANTHROPIC_BASE_URL` → TokenSaver API; Bearer = session JWT |
| **Models** | Profiles `cheap` / `default` / `strong` depend on plan (Free = allowlist) |
| **Zero-trust** | Models must be **approved** in Agent Registry — use `/tokensaver-router:approve` or `tokensaver approve --current` |
| **Flux IA (temps réel)** | **Chaque run Claude** transite le pipeline TokenSaver et est visible **en direct** dans la console (Flux IA) : étapes, tokens, coût, MCP. `/tokensaver-router:flows`, `tokensaver flows --open`, ou MCP `tokensaver_open_run_console` |
| **Agentic graph** | Handoffs multi-agents tracés en temps réel — console → *Agentic graph* (même workspace) |
| **Quotas** | Prefer `tokensaver quota` (CLI). Else MCP `tokensaver_get_usage` or `tokensaver_get_quota_usage` — paste ASCII verbatim. Never chain several quota tools. |
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
