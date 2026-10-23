# Examples

Runnable shell scripts — require `tokensaver-cli` installed and network access.

| Script | Description |
| --- | --- |
| [01-login-and-route.sh](01-login-and-route.sh) | SaaS: login → route Claude → doctor → flows |
| [02-local-selfhost.sh](02-local-selfhost.sh) | Self-host stack on localhost |
| [03-glm-open-model.sh](03-glm-open-model.sh) | Free plan + **GLM 4.7 Flash** open model |
| [04-llm-egress.sh](04-llm-egress.sh) | **OpenAI-compatible egress** (no IDE route) + Flux IA check |
| [05-vibe-loop-lab.sh](05-vibe-loop-lab.sh) | **ACP-9 BusinessLoop** lab (start/tick/precheck) + dual-path hints |

## Run

```bash
chmod +x examples/*.sh
./examples/01-login-and-route.sh
./examples/04-llm-egress.sh          # prints env; optional GET /models if key set
./examples/05-vibe-loop-lab.sh       # needs login; optional --local
./examples/05-vibe-loop-lab.sh --local
```

Scripts are **interactive** where login is required (`tokensaver login`). Set `TOKENSAVER_API_KEY` or `OPENAI_API_KEY=ts_…` to skip login if you already have a key.

## Docs

- [docs/connect-control-plane.md](../docs/connect-control-plane.md) — CLI · API · MCP · SDK
- [docs/quickstart.md](../docs/quickstart.md)
- [docs/claude-code.md](../docs/claude-code.md)
- [docs/vibe-coding-loops.md](../docs/vibe-coding-loops.md) — dual path + `tokensaver loop`
- [docs/open-models-glm.md](../docs/open-models-glm.md)
- Product: [platform.tokensaver.fr](https://platform.tokensaver.fr) → Docs → Build / Connect
