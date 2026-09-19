# Contributing to TokenSaver CLI

Thank you for your interest in TokenSaver!

## Repository model

This GitHub repository (`tokensaver-ai/tokensaver-cli`) is a **public mirror** of `packages/cli` in the private monorepo `CapIA-Labs-ai/tokensaver-platform`.

- **Day-to-day development** happens in the monorepo (source of truth).
- **This repo** is synced with `./scripts/sync-oss-cli.sh` from the monorepo root.

## How to contribute

1. **Bug reports & feature requests** — open an [issue](https://github.com/tokensaver-ai/tokensaver-cli/issues) here (preferred for OSS visibility).
2. **Pull requests on this mirror** — welcome for docs, README, and CLI fixes. Maintainers may port accepted changes back to the monorepo before the next sync.
3. **Security** — see [SECURITY.md](SECURITY.md); do **not** open public issues for vulnerabilities.

## Development setup

```bash
git clone https://github.com/tokensaver-ai/tokensaver-cli.git
cd tokensaver-cli
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

## Code style

- Python ≥ 3.10, stdlib-only runtime dependencies
- `ruff` for lint/format (line length 100)
- Tests in `tests/` with `pytest`

## Release process (maintainers)

Releases are cut from the monorepo:

1. Bump `__version__` in `src/tokensaver_cli/__init__.py`
2. Tag `cli-vX.Y.Z` on the monorepo → GitHub Action publishes to **PyPI** (`tokensaver-cli`)
3. Merge to `main` → workflow **Sync CLI OSS mirror** updates this repo (**tag `vX.Y.Z` + GitHub Release**)

Manual sync (optional): `./scripts/sync-oss-cli.sh` from the monorepo root.

Set `TOKESAVER_CLI_OSS_RELEASE=0` to skip Release creation. CI uses secret `TOKENSAVER_CLI_OSS_SYNC_TOKEN` on the monorepo; locally use `gh auth login`.

**Remote override:** `TOKESAVER_CLI_OSS_REMOTE=https://github.com/you/tokensaver.git ./scripts/sync-oss-cli.sh`

## Code of conduct

Be respectful and constructive. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
