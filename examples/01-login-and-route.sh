#!/usr/bin/env bash
# Example 01 — SaaS: login, route Claude Code, verify, open Flux IA.
# Docs: docs/quickstart.md
set -euo pipefail

echo "==> TokenSaver example 01: login and route Claude Code"
echo

if ! command -v tokensaver >/dev/null 2>&1; then
  echo "Install first: pip install -U tokensaver-cli"
  exit 1
fi

if [[ -z "${TOKENSAVER_API_KEY:-}" ]] && [[ ! -f "${HOME}/.config/tokensaver/credentials.json" ]]; then
  echo "==> Step 1: login (creates Free account + ts_… key)"
  tokensaver login
else
  echo "==> Step 1: credentials already present (or TOKENSAVER_API_KEY set)"
  tokensaver whoami || true
fi

echo
echo "==> Step 2: route Claude Code (configure; add --launch to start claude)"
tokensaver route claude

echo
echo "==> Step 3: health check"
tokensaver doctor --claude

echo
echo "==> Step 4: recent runs + Flux IA URL"
tokensaver flows

echo
echo "Done. Launch Claude with: tokensaver route claude --launch"
echo "Open dashboard: tokensaver flows --open"
