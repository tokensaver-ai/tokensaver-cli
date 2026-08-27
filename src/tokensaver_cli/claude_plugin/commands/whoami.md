---
description: Show TokenSaver identity, plan, API key, and Flux IA link
---

Run:

```bash
tokensaver whoami
# local stack:
tokensaver whoami --local
```

Report email, plan (Free / Pro / Enterprise), API host, key prefix, and Flux IA URL.
Explain that Free plan profiles default to allowlisted models (e.g. GPT-OSS 20B on `default`) while Enterprise defaults to Sonnet/Opus unless a sticky `--model` was set.
