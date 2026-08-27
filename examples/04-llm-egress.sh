#!/usr/bin/env bash
# Example 04 — LLM egress without the CLI route (OpenAI-compatible).
# Same control plane as `tokensaver route` — verify in Flux IA after a chat.
# Docs: docs/connect-control-plane.md
set -euo pipefail

API_HOST="${TOKENSAVER_API_URL:-https://api.tokensaver.fr}"
BASE="${API_HOST%/}/openai/v1"

echo "==> TokenSaver example 04: OpenAI-compatible LLM egress"
echo
echo "  Control plane path: LLM egress (not the CLI HTTP API)"
echo "  Base URL:           $BASE"
echo "  Auth:               Bearer ts_…  (TokenSaver key)"
echo

KEY="${OPENAI_API_KEY:-${TOKENSAVER_API_KEY:-}}"
if [[ -z "$KEY" ]] && command -v tokensaver >/dev/null 2>&1; then
  # Prefer explicit env; otherwise remind user to export after login.
  if [[ -f "${HOME}/.config/tokensaver/credentials.json" ]]; then
    echo "Tip: after \`tokensaver login\`, export the key shown by the console"
    echo "     or create one with: tokensaver keys create --name egress --use"
    echo "     then: export OPENAI_API_KEY=ts_…"
    echo
  fi
fi

if [[ -z "$KEY" ]]; then
  cat <<EOF
Copy-paste for any OpenAI-shaped client:

  export OPENAI_BASE_URL=$BASE
  export OPENAI_API_KEY=ts_…     # from platform.tokensaver.fr or tokensaver keys create

LangChain:

  ChatOpenAI(base_url="$BASE", api_key="ts_…")

Anthropic-shaped clients:

  export ANTHROPIC_BASE_URL=${API_HOST%/}/anthropic
  export ANTHROPIC_API_KEY=ts_…

Then open Flux IA: https://platform.tokensaver.fr → Docs/Build or tokensaver flows --open
EOF
  exit 0
fi

echo "==> GET $BASE/models (auth check)"
HTTP_CODE=$(curl -sS -o /tmp/ts-egress-models.json -w "%{http_code}" \
  -H "Authorization: Bearer $KEY" \
  "$BASE/models" || true)
echo "    HTTP $HTTP_CODE"
if [[ "$HTTP_CODE" == "200" ]]; then
  python3 -c "import json; d=json.load(open('/tmp/ts-egress-models.json')); data=d.get('data') or d.get('models') or []; print(f'    models visible: {len(data)}')" 2>/dev/null \
    || echo "    (response saved to /tmp/ts-egress-models.json)"
  echo
  echo "OK — egress accepts your key. Send a chat from LangChain / Codex / n8n,"
  echo "then verify the run in Flux IA (tokensaver flows --open)."
else
  echo "    Unexpected status — check key, plan, and API host."
  echo "    Body (first lines):"
  head -c 400 /tmp/ts-egress-models.json 2>/dev/null || true
  echo
  exit 1
fi
