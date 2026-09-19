# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| Latest PyPI `tokensaver-cli` | ✅ |
| Older CLI versions | Best effort |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email **contact@tokensaver.fr** with:

- Description of the issue
- Steps to reproduce
- Impact assessment (if known)
- Your contact for follow-up

We aim to acknowledge reports within **72 hours** and provide a remediation timeline when confirmed.

## Scope

In scope:

- `tokensaver-cli` package (this repository)
- Credential handling (`~/.config/tokensaver/credentials.json`)
- CLI interactions with `api.tokensaver.fr`, `mcp.tokensaver.fr`, `gateway.tokensaver.fr`

Out of scope for this repo (report via contact@tokensaver.fr):

- TokenSaver platform backend / console (proprietary monorepo)
- Third-party LLM providers

## Safe defaults

- Credentials file is written with mode `0600`
- Never commit `.env`, API keys, or `credentials.json` — see `.gitignore`
- Use `TOKENSAVER_API_KEY` in CI via secrets, not plaintext in repos
