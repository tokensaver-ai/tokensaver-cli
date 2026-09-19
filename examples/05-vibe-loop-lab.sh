#!/usr/bin/env bash
# Example 05 — Vibe coding lab: BusinessLoop + dual-path hints (ACP-9).
# Docs: docs/vibe-coding-loops.md · platform docs/PLAN-VIBE-CODING-DEVELOPER-SPACE.md
set -euo pipefail

echo "==> TokenSaver example 05: vibe coding loop lab"
echo

if ! command -v tokensaver >/dev/null 2>&1; then
  echo "Install first: pip install -U tokensaver-cli"
  echo "  (from monorepo: pip install -e packages/cli)"
  exit 1
fi

if [[ -z "${TOKENSAVER_API_KEY:-}" ]] && [[ ! -f "${HOME}/.config/tokensaver/credentials.json" ]]; then
  echo "No credentials. Run: tokensaver login"
  exit 1
fi

LOCAL_FLAG=()
if [[ "${1:-}" == "--local" ]] || [[ "${TOKENSAVER_MODE:-}" == "local" ]]; then
  LOCAL_FLAG=(--local)
  echo "==> Using --local API"
fi

echo "==> Step 1: start a goal_based business loop (max 3 turns)"
# shellcheck disable=SC2068
START_OUT=$(tokensaver loop start --kind goal_based --goal "lab vibe coding" --max-turns 3 ${LOCAL_FLAG[@]+"${LOCAL_FLAG[@]}"} )
echo "$START_OUT"

LOOP_ID=$(echo "$START_OUT" | awk '/loop_id:/{print $2; exit}')
if [[ -z "${LOOP_ID:-}" ]]; then
  echo "Could not parse loop_id from output." >&2
  exit 1
fi

export TOKENSAVER_LOOP_ID="$LOOP_ID"
export TOKENSAVER_LOOP_KIND=goal_based
export TOKENSAVER_LOOP_ITERATION=1

echo
echo "==> Step 2: env exports (reuse in egress / other shells)"
# shellcheck disable=SC2068
tokensaver loop env ${LOCAL_FLAG[@]+"${LOCAL_FLAG[@]}"}

echo
echo "==> Step 3: record iteration 1"
# shellcheck disable=SC2068
tokensaver loop tick --iteration 1 ${LOCAL_FLAG[@]+"${LOCAL_FLAG[@]}"}

echo
echo "==> Step 4: optional pipeline probe (headers) if API key available"
API_HOST="${TOKENSAVER_API_URL:-https://api.tokensaver.fr}"
API_HOST="${API_HOST%/}"
KEY="${TOKENSAVER_API_KEY:-}"
if [[ -z "$KEY" ]] && command -v python3 >/dev/null 2>&1; then
  KEY=$(python3 - <<'PY' 2>/dev/null || true
import json, pathlib
p = pathlib.Path.home() / ".config/tokensaver/credentials.json"
if p.is_file():
    d = json.loads(p.read_text())
    print(d.get("api_key") or "")
PY
)
fi

if [[ -n "${KEY:-}" ]]; then
  echo "    POST ${API_HOST}/api/v1/loops/${LOOP_ID}/precheck"
  HTTP=$(curl -sS -o /tmp/ts-loop-precheck.json -w "%{http_code}" \
    -X POST \
    -H "Authorization: Bearer ${KEY}" \
    -H "Content-Type: application/json" \
    -d '{"next_iteration":2}' \
    "${API_HOST}/api/v1/loops/${LOOP_ID}/precheck" || true)
  echo "    HTTP ${HTTP} — body:"
  head -c 400 /tmp/ts-loop-precheck.json 2>/dev/null || true
  echo
else
  echo "    (skip precheck curl — no API key in env/credentials)"
fi

echo
echo "==> Step 5: status"
# shellcheck disable=SC2068
tokensaver loop status --loop-id "$LOOP_ID" ${LOCAL_FLAG[@]+"${LOCAL_FLAG[@]}"}

echo
echo "Next — capture real agent traffic:"
echo "  Path A (govern):  tokensaver route claude --launch"
echo "    + MCP tokensaver_loop_* or X-Tokensaver-Loop-Id on LLM calls"
echo "  Path B (observe): export TOKENSAVER_LOOP_PRECHECK=1"
echo "    tokensaver-egress serve   # keep LOOP_* env"
echo "    tokensaver-egress claude --no-start"
echo
echo "Console: open the Boucles URL printed above → Isoler / Approve / Cancel"
echo "Done."
