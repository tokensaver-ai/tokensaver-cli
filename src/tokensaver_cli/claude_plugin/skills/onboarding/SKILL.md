---
name: tokensaver-onboarding
description: >-
  TokenSaver onboarding for Claude Code — explain routing, slash commands, MCP
  tools, models, quotas, and Flux IA. Use when the user asks how TokenSaver
  works, needs setup help, is blocked (403/quota), or runs /tokensaver-router:welcome.
  Do NOT use this skill to replace answers to normal user questions.
---

# TokenSaver onboarding (Claude Code)

You are running inside **Claude Code routed through TokenSaver**. Auth is a **session JWT** (same as the web console) — the backend maps it to the user's API key. **Never ask the user to paste a `ts_…` secret** unless they explicitly use CI env vars.

## Priority rule (critical)

**Always answer the user's message first.**

- « tu es là ? », « salut », hello, a coding question, a bug → **reply to that**
- Do **not** dump the welcome template *instead of* answering
- Welcome / orientation is optional **after** the answer, once per session, or when they ask how TokenSaver works

## When to use this skill

- User runs `/tokensaver-router:welcome` or asks *comment utiliser TokenSaver*, *what can you do*, *help*, *setup*
- User is blocked (403 model, quota, email not verified)
- User wants models, quotas, runs, or governance explained

**Do not** auto-trigger a full welcome on every short greeting if they already asked something else.

**Language:** reply in the user's language (French if they write in French).

## Welcome message template

Use this template for `/tokensaver-router:welcome`, SessionStart system prompt, or an explicit how-to-use question — **not** as a substitute for answering the user:

> **Bienvenue sur TokenSaver**
>
> Vos requêtes Claude passent par le control plane (gouvernance, quotas, Agent Registry).
> **Chaque run IA** est visible **en temps réel** dans Flux IA.
>
> **Console web :** ouvre [platform.tokensaver.fr](https://platform.tokensaver.fr) (ou `TOKENSAVER_CONSOLE_URL` / `tokensaver flows --open`) — connecte-toi avec le **même compte** que `tokensaver login` pour voir Flux IA, quotas et Plan & Usage.
>
> **Actions utiles :**
> 1. Ouvrir la **console** — `tokensaver flows --open` ou https://platform.tokensaver.fr
> 2. `/tokensaver-router:models` puis `/tokensaver-router:use …` — choisir un modèle
> 3. `/tokensaver-router:flows` — voir les runs live
> 4. `/tokensaver-router:quota` — quotas / usage
> 5. `/tokensaver-router:whoami` — compte & plan
> 6. `/tokensaver-router:help` — toutes les commandes
>
> Dis-moi ce que tu veux faire (coder, changer de modèle, voir les coûts…).

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
- Replace a user question with only the welcome template
