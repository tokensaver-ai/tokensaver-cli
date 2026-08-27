#!/usr/bin/env bash
# Example 03 — Free plan + open model GLM 4.7 Flash (no Anthropic API key).
# Model ref: openrouter/z-ai/glm-4.7-flash
# Docs: docs/open-models-glm.md
set -euo pipefail

GLM_MODEL="${TOKENSAVER_GLM_MODEL:-openrouter/z-ai/glm-4.7-flash}"

echo "==> TokenSaver example 03: Claude Code + GLM (open model)"
echo "    Model: $GLM_MODEL"
echo

if ! command -v tokensaver >/dev/null 2>&1; then
  echo "Install first: pip install -U tokensaver-cli"
  exit 1
fi

if [[ -z "${TOKENSAVER_API_KEY:-}" ]] && [[ ! -f "${HOME}/.config/tokensaver/credentials.json" ]]; then
  echo "==> Step 1: login (Free plan → allowlisted open models)"
  tokensaver login
else
  echo "==> Step 1: using existing credentials"
fi

echo
echo "==> Step 2: show Free profiles (default should be GLM on free plan)"
tokensaver whoami
tokensaver profiles

echo
echo "==> Step 3: approve GLM in Agent Registry (zero-trust)"
tokensaver approve "$GLM_MODEL"

echo
echo "==> Step 4: sticky model + rewrite Claude settings"
# --launch starts claude; omit to only configure
if [[ "${LAUNCH_CLAUDE:-}" == "1" ]]; then
  tokensaver use "$GLM_MODEL" --launch
else
  tokensaver use "$GLM_MODEL"
  echo
  echo "Configured. Start Claude with:"
  echo "  tokensaver route claude --launch"
fi

echo
echo "==> Step 5: verify routing"
tokensaver status
tokensaver doctor --claude

echo
echo "Alternative one-liners:"
echo "  tokensaver route claude --profile default --launch    # GLM on Free default profile"
echo "  tokensaver route claude --model $GLM_MODEL --launch"
echo
echo "Observability: tokensaver flows --open"
echo "In Claude: /tokensaver-router:models  /tokensaver-router:flows"
