# Connect to the TokenSaver control plane

> **One control plane. Many on-ramps.**  
> The open-source CLI is the fastest way to wire Claude Code / Cursor / Codex on a laptop.  
> APIs, SDKs, and MCP talk to the **same** governed pipeline — same quotas, Agent Registry, and [Flux IA](https://app.tokensaver.cloud) traces.

| Product Docs (full) | This guide |
| --- | --- |
| [app.tokensaver.cloud](https://app.tokensaver.cloud) → sidebar **Docs** → **Build** / **Connect** | Orientation + copy-paste recipes for OSS users |
| Same Docs after login (workspace-scoped) | Auth’d copy with your catalog & keys |

---

## Mental model

```text
  Claude Code · Cursor · Codex · LangChain · n8n · LibreChat · your app
       │              │               │              │
       │ CLI route    │ LLM egress    │ SDK / REST   │ MCP A / Gateway
       │              │ /openai/v1    │ /api/v1      │
       │              │ /anthropic    │              │
       └──────────────┴───────────────┴──────────────┘
                              │
                              ▼
              ┌───────────────────────────────────┐
              │  TokenSaver control plane (SaaS)  │
              │  cache · RAG · compression · PII  │
              │  quotas · Agent Registry · audit  │
              └───────────────────────────────────┘
                              │
                              ▼
                         Flux IA (every run)
```

### Do not confuse these surfaces

| Surface | Role | Production URL |
| --- | --- | --- |
| **CLI** (`tokensaver-cli`) | Configures *this machine* — not an HTTP API; also runs Claude agentic capture (`:8790` → causal graph) | — |
| **LLM HTTP egress** | Drop-in OpenAI / Anthropic HTTP | `https://api.tokensaver.cloud/openai/v1` · `…/anthropic` |
| **Client egress MITM** (`tokensaver-egress`) | Local HTTPS proxy → ingest / Flux IA + capture `:8789` (keep provider subscription) | localhost proxy |
| **Native API / SDK** | Full platform HTTP (`pipelines`, chat, RAG, …) | `https://control.tokensaver.cloud/api/v1` |
| **MCP tools (A)** | Platform tools (`tokensaver_chat`, quotas, runs, …) | `https://mcp.tokensaver.cloud/mcp` |
| **Trust Gateway (B)** | Govern *other* MCP servers behind TokenSaver | `https://mcp-gateway.tokensaver.cloud/mcp` |
| **A2A** | Agent-to-agent JSON-RPC | console **Docs → Build → A2A** |

---

## Choose a path

| If you… | Use | Start here |
| --- | --- | --- |
| Run **Claude Code / Cursor / Codex** on your laptop | **CLI** | [`tokensaver route …`](#1-cli-this-repository) |
| Keep a **Claude Pro/Max** (or similar) subscription and still govern traffic | **Client egress MITM** | [`tokensaver-egress`](https://github.com/tokensaver-ai/tokensaver-egress) · console **Docs → Build → LLM egress** |
| Already have an OpenAI- or Anthropic-shaped client | **LLM HTTP egress** | [#2](#2-openai-compatible-egress) · [#3](#3-anthropic-compatible-egress) |
| Build a **Python app** (RAG, sessions, policies) | **SDK** | [`tokensaver-sdk`](https://pypi.org/project/tokensaver-sdk/) · console **Docs → Build → SDK** |
| Need raw HTTP control | **Native REST** | console **Docs → Build → Native** / **API reference** |
| Want platform tools inside an agent host | **MCP A** | [#4](#4-mcp-tools-component-a) |
| Want to govern third-party MCP servers | **Trust Gateway** | [#5](#5-mcp-trust-gateway-component-b) |
| Orchestrate agents | **A2A** | console **Docs → Build → A2A** |

**Auth once:** create a `ts_…` key in the [console](https://app.tokensaver.cloud) (or `tokensaver login` / `tokensaver keys create`). Use the **same** key (or same account) everywhere so Flux IA stays coherent.

---

## Recipes

### 1. CLI (this repository)

```bash
pip install -U tokensaver-cli
tokensaver login
tokensaver route claude --launch   # also: cursor | codex | proxy | mcp
tokensaver flows --open            # prove the run hit Flux IA
```

Deep dive: [quickstart.md](quickstart.md) · [claude-code.md](claude-code.md) · console **Docs → Build → CLI** / **Connect → Claude Code**

### 2. OpenAI-compatible egress

```bash
export OPENAI_BASE_URL=https://api.tokensaver.cloud/openai/v1
export OPENAI_API_KEY=ts_…          # TokenSaver key — not an OpenAI key
```

Works with Codex, LangChain `ChatOpenAI`, n8n / Make OpenAI nodes, LibreChat, Open WebUI, many OSS UIs.

```python
# LangChain (illustrative)
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(base_url="https://api.tokensaver.cloud/openai/v1", api_key="tsv_…")
```

Runnable check: [examples/04-llm-egress.sh](../examples/04-llm-egress.sh)

### 3. Anthropic-compatible egress

```bash
export ANTHROPIC_BASE_URL=https://api.tokensaver.cloud/anthropic
export ANTHROPIC_API_KEY=ts_…
```

Claude Code, Cowork, and the Anthropic SDK hit the **same** control plane as `tokensaver route claude`.

### 4. MCP tools (Component A)

```json
{
  "mcpServers": {
    "tokensaver-tools": {
      "url": "https://mcp.tokensaver.cloud/mcp",
      "headers": { "Authorization": "Bearer tsv_…" }
    }
  }
}
```

Exposes governed tools (`tokensaver_chat`, usage, runs, catalog, …).  
Docs: console **Docs → Build → MCP** · **Connect** (Cursor, Mistral Studio, …)

### 5. MCP Trust Gateway (Component B)

Point the gateway at an upstream MCP (filesystem, DB, SaaS). Traffic is audited and policy-checked; Flux IA records tool runs.

```bash
tokensaver route mcp          # writes MCP entries for tools + gateway
# or configure mcp-gateway.tokensaver.cloud/mcp in your host — see product Docs
```

### 6. Verify in Flux IA (any path)

1. Send **one** chat or tool call through the path you chose  
2. Open [app.tokensaver.cloud](https://app.tokensaver.cloud) → **Flux IA** (`dashboard?tab=flows`)  
   — or `tokensaver flows --open` after CLI login  
3. Confirm model, tokens, cost, and pipeline steps

If nothing appears: wrong key, wrong base URL, or a different workspace account than the browser session (`tokensaver whoami`).

---

## Related links

| Resource | URL |
| --- | --- |
| Console + Docs (Build / Connect / API) | https://app.tokensaver.cloud |
| Product site | https://tokensaver.cloud |
| GitHub CLI | https://github.com/tokensaver-ai/tokensaver-cli |
| GitHub egress (MITM) | https://github.com/tokensaver-ai/tokensaver-egress |
| PyPI CLI | https://pypi.org/project/tokensaver-cli/ |
| PyPI egress | https://pypi.org/project/tokensaver-egress/ |
| PyPI SDK | https://pypi.org/project/tokensaver-sdk/ |
| This OSS connect guide | [connect-control-plane.md](connect-control-plane.md) |
