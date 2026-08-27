---
description: Log in / signup to TokenSaver (saves credentials + API key)
argument-hint: "[--local|--key ts_…]"
---

CLI-first auth (no dashboard required):

```bash
tokensaver login
# local API:
tokensaver login --local
# import existing key:
tokensaver login --key ts_…
# non-interactive signup example:
tokensaver login --email you@acme.com --signup -y
```

Then route Claude:

```bash
tokensaver route claude --launch
# or local:
tokensaver route claude --local --launch
```

Verify with `tokensaver whoami` and `tokensaver doctor --claude`.
