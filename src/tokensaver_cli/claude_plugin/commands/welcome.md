---
description: TokenSaver welcome — routing, observabilité temps réel (Flux IA), slash commands, MCP
---

Load skill **`tokensaver-onboarding`** and deliver the welcome message template.

**Must highlight:** every AI run in Claude is visible **in real time** on the TokenSaver control plane (Flux IA) — pipeline steps, tokens, cost. User can open the console while coding.

Then run (shell, for live facts):

```bash
tokensaver whoami
tokensaver status --line
tokensaver flows
```

Personalize: email/plan, current model, Flux IA URL (+ latest `flowId` if any).

Offer next steps:
1. **Watch runs live** → `tokensaver flows --open` or `/tokensaver-router:flows`
2. Not logged in → `tokensaver login` then `tokensaver route claude`
3. Model blocked → `/tokensaver-router:approve` or `tokensaver approve --current`
4. Explore models/quotas → `/tokensaver-router:models` or `/tokensaver-router:quota`

If the user asked for MCP tools, load **`tokensaver-mcp-tools`**.
