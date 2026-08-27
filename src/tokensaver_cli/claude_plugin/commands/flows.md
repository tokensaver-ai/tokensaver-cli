---
description: Open Flux IA — recent governed runs / pipeline traces
argument-hint: "[--open]"
---

Show TokenSaver Flux IA links and recent pipeline runs:

```bash
tokensaver flows
# open browser:
tokensaver flows --open
```

If MCP tools are available, also call:
- `tokensaver_list_runs` (limit 5)
- `tokensaver_get_last_run_detail` when the user wants step-by-step
- `tokensaver_open_run_console` to deep-link a run

Explain that each Claude message through TokenSaver can appear as a governed flow (cache, compression, PII, LLM, MCP). Do not invent token savings — only report what the tools/console show.
