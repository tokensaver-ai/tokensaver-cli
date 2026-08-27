#!/usr/bin/env bash
# Example 02 — Self-host: point CLI at local TokenSaver stack.
# Requires backend on :8000, MCP :8787, gateway :8788, console :3000.
# Docs: docs/quickstart.md#self-host-local-stack
set -euo pipefail

echo "==> TokenSaver example 02: local self-host mode"
echo

if ! command -v tokensaver >/dev/null 2>&1; then
  echo "Install first: pip install -U tokensaver-cli"
  exit 1
fi

export TOKENSAVER_MODE="${TOKENSAVER_MODE:-local}"
export TOKENSAVER_API_URL="${TOKENSAVER_API_URL:-http://localhost:8000}"
export TOKENSAVER_MCP_URL="${TOKENSAVER_MCP_URL:-http://localhost:8787/mcp}"
export TOKENSAVER_GATEWAY_URL="${TOKENSAVER_GATEWAY_URL:-http://localhost:8788/mcp}"
export TOKENSAVER_CONSOLE_URL="${TOKENSAVER_CONSOLE_URL:-http://localhost:3000}"

echo "Using:"
echo "  TOKENSAVER_API_URL=$TOKENSAVER_API_URL"
echo "  TOKENSAVER_MCP_URL=$TOKENSAVER_MCP_URL"
echo "  TOKENSAVER_GATEWAY_URL=$TOKENSAVER_GATEWAY_URL"
echo "  TOKENSAVER_CONSOLE_URL=$TOKENSAVER_CONSOLE_URL"
echo

if [[ -z "${TOKENSAVER_API_KEY:-}" ]] && [[ ! -f "${HOME}/.config/tokensaver/credentials.json" ]]; then
  echo "==> Login against local API"
  tokensaver login --local
else
  tokensaver whoami --local 2>/dev/null || tokensaver whoami || true
fi

echo
echo "==> Route Claude Code (local URLs)"
tokensaver route claude --local

echo
echo "==> Doctor (local surfaces)"
tokensaver doctor --claude --local

echo
echo "Launch: tokensaver route claude --local --launch"
echo "Flux IA: tokensaver flows --local --open  (same email as whoami in browser)"
