# Claude Code integration

How `tokensaver route claude` wires Claude Code to the TokenSaver control plane.

## One command

```bash
tokensaver route claude --launch
```

### What gets configured

| Target | Content |
| --- | --- |
| Claude settings (`--scope`) | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_MODEL`, MCP env vars |
| `./.mcp.json` | `tokensaver-route-tools` + `tokensaver-route-gateway` (+ FS gateway with `--with-fs`) |
| Plugin | `~/.claude/skills/tokensaver-router` — slash commands `/tokensaver-router:*` |
| UX hooks | Status line + SessionStart → `tokensaver status` |

### Scope

| Flag | Settings file |
| --- | --- |
| `--scope user` (default) | `~/.claude/settings.json` |
| `--scope project` | `.claude/settings.json` |
| `--scope local` | `.claude/settings.local.json` |

### Useful flags

```bash
tokensaver route claude --scope project --profile default --with-fs --launch
tokensaver route claude --model openrouter/z-ai/glm-4.7-flash --launch
tokensaver route claude --no-plugin --launch          # skip slash-command plugin
tokensaver route claude --local --launch              # self-host URLs
tokensaver route claude -- --model anthropic/claude-sonnet-4-6   # extra args → claude binary
```

## Model profiles

```bash
tokensaver profiles
tokensaver models
```

Profiles depend on your **plan** (`plan_slug` from login, or `TOKENSAVER_PLAN=free`):

| Profile | Paid default | Free allowlist |
| --- | --- | --- |
| `cheap` | `openai/gpt-4.1-mini` | `openrouter/openai/gpt-5-nano` |
| `default` | `anthropic/claude-sonnet-4-6` | **`openrouter/openai/gpt-oss-20b`** (GPT-OSS 20B) |
| `strong` | `anthropic/claude-opus-4-6` | `openrouter/deepseek/deepseek-chat-v3-0324` |

```bash
tokensaver route claude --profile default --launch
tokensaver use openrouter/z-ai/glm-4.7-flash --launch
```

After `tokensaver use …`, a bare `route claude --launch` keeps the **sticky** model.

Custom overrides: `~/.config/tokensaver/route/profiles.json`

## Agent Registry (zero-trust)

Models must be **approved** in the Agent Registry or Claude gets `403` / quarantined errors.

When you run `tokensaver route claude --launch` (or `tokensaver use …`) in a terminal, if the model is **not yet approved**, the CLI prompts:

```text
────────────────────────────────────────
  TokenSaver zero-trust policy
────────────────────────────────────────
  Model   openrouter/openai/gpt-oss-20b
  Status  not registered

  Unapproved models are blocked until you allow them in the
  Agent Registry. This is TokenSaver's zero-trust security
  policy — approve once to continue with this model.

  Approve this model now? [Y/n]
```

Answer **Y** to approve and continue; **n** cancels launch.

Manual / non-interactive:

```bash
tokensaver approve openrouter/z-ai/glm-4.7-flash
tokensaver approve --current
tokensaver catalog pending
TOKENSAVER_AUTO_APPROVE=1 tokensaver route claude --launch   # skip prompt (CI/scripts)
```

For gateway models (`openrouter/…`), routing also sets `CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1` in Claude settings to suppress the yellow “unrecognized model” banner.

**Email verification:** until your inbox is confirmed, approve and API calls return **403** — verify at [platform.tokensaver.fr](https://platform.tokensaver.fr) (Account settings).

**Already inside Claude Code with a 403?** Open a second terminal and run `tokensaver approve --current` (slash commands need a working model).
## Slash commands (plugin)

After routing, in Claude Code:

| Slash | Purpose |
| --- | --- |
| `/tokensaver-router:models` | List models + profiles |
| `/tokensaver-router:use` | Switch model (sticky) |
| `/tokensaver-router:flows` | Flux IA + recent runs |
| `/tokensaver-router:quota` | Key + quotas (MCP) |
| `/tokensaver-router:cache` | Cache stats (MCP) |
| `/tokensaver-router:doctor` | Health checks |
| `/tokensaver-router:approve` | Approve current model |

If the active model is blocked, run CLI commands in a terminal (slash needs a working model).

## MCP servers (injected)

| Server | URL (SaaS) | Role |
| --- | --- | --- |
| `tokensaver-route-tools` | `https://mcp.tokensaver.fr/mcp` | TokenSaver tools (`tokensaver_chat`, quotas, runs, …) |
| `tokensaver-route-gateway` | `https://gateway.tokensaver.fr/mcp` | Trust Gateway (filesystem, governed tools) |
| `tokensaver-route-fs` | gateway + cwd | Only with `--with-fs` |

Auth: `Authorization: Bearer ts_…` (from credentials or `TOKENSAVER_API_KEY`).

## Health checks

```bash
tokensaver doctor --claude
```

Checks API key, Anthropic-compatible `/v1/models`, MCP tools, and gateway reachability.

## Undo

```bash
tokensaver unroute claude
```

Restores files from `~/.config/tokensaver/route/backups/`.

## See also

- [Open models (GLM)](open-models-glm.md)
- [Quick start](quickstart.md)
- [Models & Free plan](models-and-free-plan.md)
- [Control plane — Flux IA & agentic graph (live)](../README.md#control-plane--live-observability)
- [Product overview](https://tokensaver.fr)
