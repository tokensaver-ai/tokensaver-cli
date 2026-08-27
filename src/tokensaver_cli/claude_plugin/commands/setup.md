---
description: Configure Claude Code to route through TokenSaver (login, settings, MCP, model profile)
---

If TokenSaver is not configured yet, start with CLI login (no dashboard required):

```bash
tokensaver login
# or: tokensaver login --email you@acme.com --signup -y
```

This creates a Free account (or signs in), mints a `ts_…` API key, and saves
`~/.config/tokensaver/credentials.json`.

Then route Claude Code:

```bash
tokensaver route claude --scope project --profile default --with-fs
```

Useful variants:

- Cheap testing model: `tokensaver route claude --profile cheap`
- Explicit model: `tokensaver route claude --model openai/gpt-4.1-mini`
- Local self-host: `tokensaver route claude --local --with-fs`
- Import existing key: `tokensaver login --key ts_…`

Verify:

```bash
tokensaver whoami
tokensaver doctor --claude
tokensaver status
```

Open governed runs in Flux IA (printed by `tokensaver status` / `whoami`).
