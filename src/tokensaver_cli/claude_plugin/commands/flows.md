---
description: Flux IA — voir en temps réel tous les runs IA exécutés dans Claude (control plane)
argument-hint: "[--open]"
---

**Message clé pour l'utilisateur :** avec TokenSaver, **chaque message et run IA** passé par Claude Code est tracé **en temps réel** dans le control plane ([Flux IA](https://platform.tokensaver.fr)) — étapes du pipeline (cache, compression, PII, LLM, MCP), tokens, coût, gouvernance.

Show links and recent runs:

```bash
tokensaver flows
# ouvrir la console en direct pendant que Claude travaille :
tokensaver flows --open
```

If MCP tools are available, also call:
- `tokensaver_list_runs` (limit 5) — liste des runs récents
- `tokensaver_get_last_run_detail` — détail pas-à-pas du dernier run (coller l'ASCII tel quel)
- `tokensaver_open_run_console` — deep link navigateur vers un run précis
- `tokensaver_get_monitoring_run` — étapes détaillées si `request_id` connu

Explain:
1. **Temps réel** — la console se met à jour pendant la session Claude (même email que `tokensaver whoami`)
2. **Multi-agents** — sidebar console → **Agentic graph** pour les handoffs entre agents
3. Ne pas inventer d'économies de tokens — seulement ce que les outils/console affichent

Invite the user to keep Flux IA open in a browser tab while coding to watch runs live.
