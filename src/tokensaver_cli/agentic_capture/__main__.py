"""``python -m tokensaver_cli.agentic_capture`` — serve capture side-channel."""

from __future__ import annotations

import sys

from tokensaver_cli.agentic_capture.server import run_capture_serve


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    # Accept bare invoke or ``serve`` subcommand.
    if args and args[0] in ("serve", "run"):
        args = args[1:]
    raise SystemExit(run_capture_serve())


if __name__ == "__main__":
    main()
