---
description: Message d'accueil TokenSaver — guide des actions (models, Flux IA, quotas)
---

Load skill **`tokensaver-onboarding`** and **immediately** print the welcome message template
as your reply (do not only run shell commands first).

Then optionally enrich with:

```bash
tokensaver whoami
tokensaver status --line
```

Highlight:
- **Flux IA temps réel** — `/tokensaver-router:flows` or `tokensaver flows --open`
- Models — `/tokensaver-router:models` + `/tokensaver-router:use …`
- Quotas — `/tokensaver-router:quota`
- Help — `/tokensaver-router:help`

End by asking what the user wants to do next.
