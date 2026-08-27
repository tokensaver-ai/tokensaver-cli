---
description: Show TokenSaver API key quotas and usage
---

Prefer MCP tools (paste ASCII dashboards as-is, do not rewrite into prose):

1. `tokensaver_get_api_key_overview` — full key dashboard (primary)
2. Or `tokensaver_get_quota_usage` if the user only asks for quotas

If MCP is unavailable, fall back to:

```bash
tokensaver whoami
tokensaver doctor
```

and the Flux IA / console usage pages from `tokensaver status`.
