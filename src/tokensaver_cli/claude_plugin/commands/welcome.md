---
description: Message d'accueil TokenSaver — guide des actions (models, Flux IA, quotas)
---

Load skill **`tokensaver-onboarding`** and **immediately** print the welcome message template
as your reply (do not only run shell commands first).

Include a clear invite to **open / sign in to the web console** with the same account as
`tokensaver login` — prefer `tokensaver flows --open`, or the console URL from
`TOKENSAVER_CONSOLE_URL` / https://platform.tokensaver.fr.

Then optionally enrich with:

```bash
tokensaver whoami
tokensaver status --line
tokensaver flows --open
```

Highlight:
- **Console web** — se connecter (même compte JWT) pour Flux IA, quotas, Plan & Usage
- **Flux IA temps réel** — `/tokensaver-router:flows` or `tokensaver flows --open`
- Models — `/tokensaver-router:models` + `/tokensaver-router:use …`
- Quotas — `/tokensaver-router:quota`
- Help — `/tokensaver-router:help`

End by asking what the user wants to do next.
