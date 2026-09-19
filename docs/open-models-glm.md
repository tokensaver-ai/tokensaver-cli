# Open models on Free plan — GLM 4.7 Flash

Use **open-source / open-weight models** through TokenSaver without an Anthropic or OpenAI API key. On the **Free** plan, the CLI **`default`** profile is **`openrouter/openai/gpt-oss-20b`**; this guide covers **GLM 4.7 Flash** as a fast alternative.

**Full Free list:** [models-and-free-plan.md](models-and-free-plan.md).

## GLM 4.7 Flash (optional)

After `tokensaver login` on Free, switch to GLM explicitly:

```text
openrouter/z-ai/glm-4.7-flash
```

(Z.AI **GLM 4.7 Flash** — fast, allowlisted for Free.)

Verify:

```bash
tokensaver whoami          # plan: free
tokensaver profiles        # default → openrouter/z-ai/glm-4.7-flash
tokensaver models
```

## Quick path (Claude Code + GLM)

```bash
pip install -U tokensaver-cli
tokensaver login

# Explicit GLM (approve + sticky model + rewrite Claude settings)
tokensaver use openrouter/z-ai/glm-4.7-flash --launch

# Or profile default (same model on Free)
tokensaver route claude --profile default --launch
```

`tokensaver use` calls `approve` internally and sets **sticky** model — the next `route claude --launch` keeps GLM.

## Step by step (understand each step)

```bash
# 1 — Account + ts_… key
tokensaver login

# 2 — Approve GLM in Agent Registry (zero-trust)
tokensaver approve openrouter/z-ai/glm-4.7-flash

# 3 — Route Claude to TokenSaver + GLM
tokensaver route claude --model openrouter/z-ai/glm-4.7-flash --launch

# 4 — Confirm model in settings
tokensaver status
tokensaver doctor --claude
```

## Other Free allowlist models

See the **full list of 15 models**: [models-and-free-plan.md](models-and-free-plan.md).

Profile shortcuts:

| Profile | Model ref | Notes |
| --- | --- | --- |
| `cheap` | `openrouter/openai/gpt-5-nano` | Light / low cost |
| `default` | `openrouter/openai/gpt-oss-20b` | **Free CLI default** |
| `glm` (via `use`) | `openrouter/z-ai/glm-4.7-flash` | Fast GLM alternative |
| `strong` | `openrouter/deepseek/deepseek-chat-v3-0324` | Stronger open model |

```bash
tokensaver use default          # GLM on Free
tokensaver use strong --launch  # DeepSeek on Free
tokensaver route claude --profile cheap --launch
```

## Force Free profiles (testing)

If `whoami` does not show `free` but you want allowlist behaviour:

```bash
export TOKENSAVER_PLAN=free
tokensaver profiles
```

## Zero-trust 403

If Claude reports the model is quarantined or not registered:

```bash
tokensaver approve --current
# or
tokensaver catalog pending
tokensaver catalog approve openrouter/z-ai/glm-4.7-flash
```

## Observability

Every GLM run goes through the governed pipeline — visible in Flux IA:

```bash
tokensaver flows --open   # Flux IA tab (live)
```

**Control plane:** [platform.tokensaver.fr/en/login](https://platform.tokensaver.fr/en/login) · **Agentic graph:** console sidebar → *Agentic graph* (`/execution-graph?period=7d`) for multi-agent handoffs in real time.

In Claude: `/tokensaver-router:flows` or ask for *"cost of the last run"* (MCP `tokensaver_get_last_run_detail`).

## No Anthropic subscription required

`tokensaver route claude` sets:

- `ANTHROPIC_BASE_URL` → TokenSaver (`api.tokensaver.fr/anthropic`)
- `ANTHROPIC_AUTH_TOKEN` → your `ts_…` key
- `ANTHROPIC_API_KEY` → cleared

Traffic uses your **TokenSaver** key and plan quotas — not Claude Pro billing for that **routed** path.

To keep a **Claude Pro / Max** subscription and still govern traffic, use **egress MITM** instead of `route` (passthrough to Anthropic + `TOKENSAVER_API_KEY` for Flux IA / policies) — see the platform runbook [RUNBOOK-EGRESS-ACP-4.md](../../../docs/RUNBOOK-EGRESS-ACP-4.md) §3.3.1.

## Runnable script

See [examples/03-glm-open-model.sh](../examples/03-glm-open-model.sh).

## Paid / BYOK

On paid plans, profiles default to Sonnet/Opus/GPT — you can still `use` any approved catalog model:

```bash
tokensaver use openrouter/z-ai/glm-4.7-flash --launch
```

## See also

- [Models & Free plan (600+ catalogue, 15 free models)](models-and-free-plan.md)
- [Claude Code integration](claude-code.md)
- [Quick start](quickstart.md)
- [Product — model-agnostic pipeline](https://tokensaver.fr)
