# Quick start

Get from zero to a routed Claude Code session in about a minute.

> Prefer APIs, LangChain, or MCP instead of the CLI? See **[connect-control-plane.md](connect-control-plane.md)** — same control plane, other on-ramps.

## Prerequisites

- Python **≥ 3.10**
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (for `--launch`)
- Network access to `api.tokensaver.fr` (SaaS mode)

## 1. Install

```bash
pip install -U tokensaver-cli
tokensaver --help
```

No runtime dependencies — stdlib only.

## 2. Sign up or sign in

```bash
tokensaver login
```

This creates a **Free** workspace (if new) and saves:

- API key `ts_…` (shown once — copy it)
- Session JWT (for `keys list`, etc.)
- `workspace_id` for Flux IA deep links

**Free plan** includes **15 hosted models** (no OpenAI/Anthropic key). **Pro/BYOK** opens the full **600+** Agent Registry — [models & Free plan](models-and-free-plan.md).

File: `~/.config/tokensaver/credentials.json` (mode `0600`).

**Non-interactive signup:**

```bash
tokensaver login --email you@example.com --password 'your-password' --signup -y
```

**Import an existing key:**

```bash
tokensaver login --key ts_your_existing_key
```

## 3. Route Claude Code

```bash
tokensaver route claude --launch
```

This command:

1. Backs up your Claude settings (restored by `unroute`)
2. Points Claude at `https://api.tokensaver.fr/anthropic`
3. Writes `./.mcp.json` (MCP tools + Trust Gateway)
4. Installs the `tokensaver-router` plugin (slash commands)
5. Launches `claude` (unless you omit `--launch`)

## 4. Verify

```bash
tokensaver whoami
tokensaver doctor --claude
tokensaver status
```

## 5. Observability (Flux IA & agentic graph)

**Control plane:** [platform.tokensaver.fr](https://platform.tokensaver.fr) — [sign up](https://platform.tokensaver.fr/en/signup) · [log in](https://platform.tokensaver.fr/en/login)

```bash
tokensaver flows          # recent runs + Flux IA URL
tokensaver flows --open   # open Flux IA in browser (live)
```

| Console view | What you see | URL pattern (after login) |
| --- | --- | --- |
| **Flux IA** | Pipeline steps, cache, PII, LLM, MCP — updates as agents run | `…/en/{workspaceId}/dashboard?tab=flows` |
| **Agentic graph** | Multi-agent handoffs, tool runs, audit graph (real time) | `…/en/{workspaceId}/execution-graph?period=7d` |

`tokensaver flows --open` resolves your `workspace_id` from `tokensaver login` and opens Flux IA. For the **agentic graph**, open the console → sidebar → **Agentic graph** (same workspace).

Use the **same email** in the browser as `tokensaver whoami` — otherwise Flux IA links may show *flow not found*.

## Undo routing

```bash
tokensaver unroute claude   # restore Claude settings + MCP backups
tokensaver logout           # remove local credentials only
```

## Environment override

```bash
export TOKENSAVER_API_KEY=ts_…   # overrides credentials file
export TOKENSAVER_NO_BANNER=1    # hide ASCII banner on CLI start
```

## Next steps

- [Connect — CLI · API · MCP · SDK](connect-control-plane.md) (same control plane, other on-ramps)
- [Models & Free plan — 600+ catalogue, 15 free models](models-and-free-plan.md)
- [Claude Code deep-dive](claude-code.md)
- [GLM & open models on Free plan](open-models-glm.md)
- [Shell examples](../examples/README.md) (incl. `04-llm-egress.sh`)
- [Documentation index](README.md)
- Product Docs: [platform.tokensaver.fr](https://platform.tokensaver.fr) → **Docs → Build / Connect**

## Self-host (local stack)

Append `--local` to commands when your TokenSaver stack runs on localhost:

```bash
tokensaver login --local
tokensaver route claude --local --launch
```

See [examples/02-local-selfhost.sh](../examples/02-local-selfhost.sh).
