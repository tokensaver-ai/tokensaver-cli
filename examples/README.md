# Examples

Runnable shell scripts — require `tokensaver-cli` installed and network access.

| Script | Description |
| --- | --- |
| [01-login-and-route.sh](01-login-and-route.sh) | SaaS: login → route Claude → doctor → flows |
| [02-local-selfhost.sh](02-local-selfhost.sh) | Self-host stack on localhost |
| [03-glm-open-model.sh](03-glm-open-model.sh) | Free plan + **GLM 4.7 Flash** open model |

## Run

```bash
chmod +x examples/*.sh
./examples/01-login-and-route.sh
```

Scripts are **interactive** where login is required (`tokensaver login`). Set `TOKENSAVER_API_KEY` to skip login if you already have a key.

## Docs

- [docs/quickstart.md](../docs/quickstart.md)
- [docs/claude-code.md](../docs/claude-code.md)
- [docs/open-models-glm.md](../docs/open-models-glm.md)
