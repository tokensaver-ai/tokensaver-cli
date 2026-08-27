# Models & Free plan — 600+ catalog, 15 free models

TokenSaver exposes a large **Agent Registry** (OpenAI- and Anthropic-compatible APIs). The CLI lets you pick models via **`tokensaver models`**, **`tokensaver use`**, and **`--profile` / `--model`** on `route claude`.

## At a glance

| | **Free** | **Pro / Enterprise (BYOK)** |
| --- | --- | --- |
| **Catalog** | **15** hosted models (OpenRouter allowlist) | **600+** active models (full catalog) |
| **Provider API key** | No — included in the Free plan | Yes — your OpenAI, Anthropic, OpenRouter keys, … |
| **Model cost** | Free plan quotas | Your provider rates + TokenSaver governance |
| **CLI discovery** | `tokensaver models` (filtered list) | `tokensaver models` (full catalog) |

The platform catalog lists **647 models**; marketing uses **600+** for plans with full catalog access.

## Free plan — 15 included models

No Anthropic, OpenAI, or OpenRouter key to configure: after `tokensaver login`, these models go through **api.tokensaver.fr** with your **`ts_…`** key.

CLI reference: `openrouter/` prefix + `model_id` (e.g. `openrouter/z-ai/glm-4.7-flash`).

| Model (CLI ref) | Provider / family | Notes |
| --- | --- | --- |
| `openrouter/openai/gpt-5-nano` | OpenAI | Light, **`cheap`** profile |
| `openrouter/openai/gpt-4.1-nano` | OpenAI | Very economical |
| `openrouter/openai/gpt-4o-mini` | OpenAI | Light multimodal |
| `openrouter/openai/gpt-oss-20b` | OpenAI | Open-weight · **CLI `default` profile** |
| `openrouter/z-ai/glm-4.7-flash` | Z.AI GLM | Fast GLM — `tokensaver use openrouter/z-ai/glm-4.7-flash` |
| `openrouter/deepseek/deepseek-v4-flash` | DeepSeek | Fast |
| `openrouter/deepseek/deepseek-chat-v3-0324` | DeepSeek | **`strong`** profile |
| `openrouter/google/gemini-2.5-flash-lite` | Google Gemini | Flash lite |
| `openrouter/google/gemma-3-4b-it` | Google Gemma | Small instruct |
| `openrouter/meta-llama/llama-3.1-8b-instruct` | Meta Llama | 8B instruct |
| `openrouter/qwen/qwen-2.5-7b-instruct` | Qwen | 7B instruct |
| `openrouter/mistralai/mistral-nemo` | Mistral | Nemo |
| `openrouter/mistralai/ministral-3b-2512` | Mistral | Ministral 3B |
| `openrouter/amazon/nova-micro-v1` | Amazon Nova | Micro |
| `openrouter/bytedance-seed/seed-2.0-mini` | ByteDance Seed | Mini |

Free availability and limits are defined by the TokenSaver plan and may change. Always check the live list:

```bash
tokensaver whoami          # plan: free
tokensaver models          # catalog filtered for your key
tokensaver profiles        # cheap / default / strong
```

## CLI shortcuts (profiles)

On the **Free** plan, built-in profiles point to the allowlist:

| Profile | Model | Usage |
| --- | --- | --- |
| **`cheap`** | `openrouter/openai/gpt-5-nano` | Minimal cost |
| **`default`** | `openrouter/openai/gpt-oss-20b` | **GPT-OSS 20B** — default after login |
| **`strong`** | `openrouter/deepseek/deepseek-chat-v3-0324` | More capable model |

```bash
tokensaver use default --launch              # GPT-OSS 20B + approve + Claude
tokensaver route claude --profile cheap --launch
tokensaver use openrouter/z-ai/glm-4.7-flash --launch   # GLM alternative
```

GLM details: [open-models-glm.md](open-models-glm.md).

## Claude Code without an Anthropic subscription

**`tokensaver route claude`** redirects Claude Code to TokenSaver:

- `ANTHROPIC_BASE_URL` → `https://api.tokensaver.fr/anthropic`
- `ANTHROPIC_AUTH_TOKEN` → your **`ts_…`** key
- No Claude Pro billing on this **routed** path

TokenSaver is a **SaaS control plane** (PII governance, quotas, cache, Flux IA, Agent Registry). The **Free** plan includes **15 hosted models**; the **600+** catalog opens with **Pro/BYOK** and your provider keys.

```bash
pip install -U tokensaver-cli
tokensaver login
tokensaver route claude --profile default --launch   # GPT-OSS 20B on Free
```

### Keep Claude Pro / Max + govern via egress MITM

To keep Anthropic subscription billing while capturing / governing traffic (optional
`model_routing` to your own models):

```bash
# Proxy: ./scripts/start-egress.sh --mode mitm  (monorepo) — see RUNBOOK-EGRESS-ACP-4 §3.3.1
export HTTPS_PROXY=http://localhost:8888
export HTTP_PROXY=http://localhost:8888
export NODE_EXTRA_CA_CERTS=$HOME/.tokensaver-egress/ca/ca.crt
export TOKENSAVER_API_KEY=ts_…   # governance only — Claude /login = Pro session
claude
```

No `ANTHROPIC_API_KEY` required when Claude is already logged in with Pro/Max.

## Supported agents

| Agent | Command | Models |
| --- | --- | --- |
| **Claude Code** | `tokensaver route claude --launch` | `/model`, `--profile`, `--model`, `tokensaver use` |
| **Cursor** | `tokensaver route cursor` | OpenAI-compatible URL override |
| **Codex** | `tokensaver route codex --launch` | `OPENAI_BASE_URL` + `ts_…` key |
| **Other client** | `tokensaver route proxy` | OpenAI / Anthropic URLs to copy |

## Pro / BYOK — 600+ catalog

On **Pro** or **Enterprise**, connect your provider keys (console → Settings) and use the **full active catalog**:

```bash
tokensaver models                    # full list (plan-filtered)
tokensaver use anthropic/claude-sonnet-4-6 --launch
tokensaver catalog list
tokensaver approve openrouter/…      # zero-trust if model is quarantined
```

Default paid profiles: `cheap` → GPT-4.1 mini, `default` → Claude Sonnet, `strong` → Claude Opus.

## Zero-trust 403

Model not registered / quarantined in the Agent Registry:

- On `tokensaver route claude --launch` (TTY): interactive **Approve this model now? [Y/n]**
- Or manually:

```bash
tokensaver approve --current
tokensaver catalog pending
tokensaver catalog approve openrouter/z-ai/glm-4.7-flash
```

## See also

- [Quick start](quickstart.md)
- [GLM & open models](open-models-glm.md)
- [Claude Code](claude-code.md)
- [Product — plans](https://tokensaver.fr)
