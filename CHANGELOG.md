# Changelog

All notable changes to `tokensaver-cli` are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.26] - 2026-09-11

- fix(cli): skip catalog picker on explicit use/--model (0.3.24)
- feat(env): update console base URL and add ArkaneCloud support
- fix(cli): ignore legacy sticky console :3000 for local doctor
- feat(cli): resolve local console URL and ship 0.3.22
- feat(cli): enhance documentation and welcome message context
- feat(cli): enhance welcome message handling and session context
- feat(cli): update quota documentation and usage guidelines
- feat(cli): streamline welcome context and onboarding process
- feat(cli): update welcome messages and onboarding guidance
- feat(cli): enhance model approval flow for free plan users
- feat(cli): enhance model selection and approval for free plan users
- fix(cli): SaaS login ignores leftover TOKENSAVER_MODE=local
- feat(cli): improve API host and console URL resolution logic
- feat(cli): refine model selection for free plan users


## [0.3.25] - 2026-09-11

- fix(cli): skip catalog picker on explicit use/--model (0.3.24)
- feat(env): update console base URL and add ArkaneCloud support
- fix(cli): ignore legacy sticky console :3000 for local doctor
- feat(cli): resolve local console URL and ship 0.3.22
- feat(cli): enhance documentation and welcome message context
- feat(cli): enhance welcome message handling and session context
- feat(cli): update quota documentation and usage guidelines
- feat(cli): streamline welcome context and onboarding process
- feat(cli): update welcome messages and onboarding guidance
- feat(cli): enhance model approval flow for free plan users
- feat(cli): enhance model selection and approval for free plan users
- fix(cli): SaaS login ignores leftover TOKENSAVER_MODE=local
- feat(cli): improve API host and console URL resolution logic
- feat(cli): refine model selection for free plan users


## [0.3.24] - 2026-09-11

- fix(cli): `tokensaver use <model>` / `--model` approve that ref directly (no full catalog picker)
- fix(cli): do not inject `HTTPS_PROXY=:8888` into Claude settings (Connection refused when egress is down)

## [0.3.23] - 2026-09-11

- fix(cli): ignore legacy sticky `console_url` on `:3000` so local doctor defaults to `:7337` outside the monorepo

## [0.3.22] - 2026-09-11

- feat(cli): resolve local console URL from `TOKENSAVER_CONSOLE_URL`, `CONSOLE_BASE_URL`, or monorepo `apps/console/.env.local` `PORT`
- chore(cli): default local console port `http://localhost:7337` (was `:3000`)
- docs(cli): document console URL env / discovery for local self-host

## [0.3.14] - 2026-08-27

- fix(cli): bare `login` / sticky SaaS credentials ignore leftover `TOKENSAVER_MODE=local` and monorepo localhost env (no more silent local hijack)

## [0.3.13] - 2026-08-27

- feat(cli): improve API host / console URL resolution (ignore localhost `TOKENSAVER_API_URL` without `--local`)

## [0.3.12] - 2026-08-27

- feat(cli): Free plan model picker uses the Free allowlist only (not full OpenRouter catalog)
- fix(ci): GitHub Release create then upload assets (avoid 422 blocking PyPI)

## [0.3.11] - 2026-08-27

- feat(cli): enhance model approval process and introduce quota command
- fix(cli): refine environment variable handling in agents.py
- feat(cli): add prompt nudge feature and enhance welcome message handling
- feat: enhance CLI release process and command functionality
- feat: enhance TokenSaver CLI with new welcome JSON feature and improved command descriptions
- refactor: enhance authentication handling for session JWTs and API keys
- docs: update CLI README for improved clarity and visual presentation
- docs: enhance egress and CLI documentation for clarity and updates
- docs: update quota limits and model references in documentation
- docs: update CLI documentation links for consistency and clarity
- docs: update CLI documentation for improved clarity and navigation
- docs: update CLI README logo for improved branding


## [0.3.10] - 2026-08-27

- fix(cli): refine environment variable handling in agents.py
- feat(cli): add prompt nudge feature and enhance welcome message handling
- feat: enhance CLI release process and command functionality
- feat: enhance TokenSaver CLI with new welcome JSON feature and improved command descriptions
- refactor: enhance authentication handling for session JWTs and API keys
- docs: update CLI README for improved clarity and visual presentation
- docs: enhance egress and CLI documentation for clarity and updates
- docs: update quota limits and model references in documentation
- docs: update CLI documentation links for consistency and clarity
- docs: update CLI documentation for improved clarity and navigation
- docs: update CLI README logo for improved branding
- docs: update CLI README to enhance visual branding and content clarity
- docs: enhance CLI release process and GitHub Actions workflow


## [0.3.9] - 2026-08-27

- feat(cli): add prompt nudge feature and enhance welcome message handling
- feat: enhance CLI release process and command functionality
- feat: enhance TokenSaver CLI with new welcome JSON feature and improved command descriptions
- refactor: enhance authentication handling for session JWTs and API keys
- docs: update CLI README for improved clarity and visual presentation
- docs: enhance egress and CLI documentation for clarity and updates
- docs: update quota limits and model references in documentation
- docs: update CLI documentation links for consistency and clarity
- docs: update CLI documentation for improved clarity and navigation
- docs: update CLI README logo for improved branding
- docs: update CLI README to enhance visual branding and content clarity
- docs: enhance CLI release process and GitHub Actions workflow
- docs: update CLI release process and sync script documentation
- feat(auth): add email verification handling to login process


## [0.3.8] - 2026-08-27

- feat: enhance CLI release process and command functionality
- feat: enhance TokenSaver CLI with new welcome JSON feature and improved command descriptions
- refactor: enhance authentication handling for session JWTs and API keys
- docs: update CLI README for improved clarity and visual presentation
- docs: enhance egress and CLI documentation for clarity and updates
- docs: update quota limits and model references in documentation
- docs: update CLI documentation links for consistency and clarity
- docs: update CLI documentation for improved clarity and navigation
- docs: update CLI README logo for improved branding
- docs: update CLI README to enhance visual branding and content clarity
- docs: enhance CLI release process and GitHub Actions workflow
- docs: update CLI release process and sync script documentation
- feat(auth): add email verification handling to login process
- docs: update TokenSaver CLI documentation to reflect new model offerings and free plan details
- feat(entrypoint): implement PII model prefetching at startup


### Added

- OSS mirror README (hero banner, demo GIF, agent matrix)
- `llms.txt`, `CONTRIBUTING.md`, `SECURITY.md`, GitHub CI workflow

## [0.3.7] - 2026-03-XX

- Claude Code routing with MCP tools + Trust Gateway + `tokensaver-router` plugin
- `tokensaver login` Free signup flow
- Flux IA observability (`tokensaver flows`)
- Agent Registry (`approve`, `catalog`, `use`)
- Cursor, Codex, proxy, and MCP-only routing targets

[Unreleased]: https://github.com/tokensaver-ai/tokensaver-cli/compare/v0.3.26...HEAD
[0.3.26]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.26
[0.3.25]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.25
[0.3.14]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.14
[0.3.13]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.13
[0.3.12]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.12
[0.3.11]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.11
[0.3.10]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.10
[0.3.9]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.9
[0.3.8]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.8
[0.3.7]: https://github.com/tokensaver-ai/tokensaver-cli/releases/tag/v0.3.7
