---
description: List TokenSaver Router slash commands and CLI equivalents
---

Print this catalogue for the user:

| Slash | Purpose | CLI |
|-------|---------|-----|
| `/tokensaver-router:models` | List profiles + catalogue | `tokensaver models` |
| `/tokensaver-router:use` | Set model (sticky) + approve | `tokensaver use …` |
| `/tokensaver-router:model` | Alias of use | `tokensaver use …` |
| `/tokensaver-router:approve` | Agent Registry approve | `tokensaver approve …` |
| `/tokensaver-router:catalog` | List/approve registry | `tokensaver catalog …` |
| `/tokensaver-router:status` | Route statusline | `tokensaver status` |
| `/tokensaver-router:whoami` | Identity + plan | `tokensaver whoami` |
| `/tokensaver-router:flows` | Flux IA / recent runs | `tokensaver flows` |
| `/tokensaver-router:pipeline` | Flux IA pipeline hint | `tokensaver status` |
| `/tokensaver-router:quota` | Quotas / key overview | MCP `tokensaver_get_api_key_overview` |
| `/tokensaver-router:cache` | Cache stats | MCP `tokensaver_cache_stats` |
| `/tokensaver-router:login` | Login / signup | `tokensaver login` |
| `/tokensaver-router:keys` | API keys | `tokensaver keys …` |
| `/tokensaver-router:setup` | Full route setup | `tokensaver route claude` |
| `/tokensaver-router:doctor` | Health checks | `tokensaver doctor --claude` |
| `/tokensaver-router:unroute` | Restore Claude settings | `tokensaver unroute claude` |
| `/tokensaver-router:help` | This list | — |

Tip: if the current model is blocked (credits / 403), run the **CLI** commands in a terminal — slash prompts need a working model.
