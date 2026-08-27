---
description: Show TokenSaver API key quotas and usage
---

Prefer the fast CLI (one API call) — paste the output as-is:

```bash
tokensaver quota
```

For detailed quota dimensions:

```bash
tokensaver quota --full
```

If the CLI is unavailable, use **one** MCP tool only (do not chain several):

1. Simple « usage » / consommation → `tokensaver_get_usage`
2. Quotas + limits → `tokensaver_get_quota_usage`
3. Full key dashboard → `tokensaver_get_api_key_overview` (only if asked for everything)

Paste ASCII dashboards verbatim. Never call overview + usage + consumption together.
