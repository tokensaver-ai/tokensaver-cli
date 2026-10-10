"""Claude Code agentic capture for tokensaver-cli (independent of tokensaver-egress).

Local HTTP side-channel (default :8790) that accepts hooks + OTLP and ships
envelopes to ``POST /api/v1/egress/agentic-events`` — same contract as the
egress capture path, without importing tokensaver-egress.
"""

from tokensaver_cli.agentic_capture.server import (
    capture_client_environ,
    capture_enabled,
    capture_health_ok,
    capture_port,
    ensure_capture_running,
    run_capture_serve,
)

__all__ = [
    "capture_client_environ",
    "capture_enabled",
    "capture_health_ok",
    "capture_port",
    "ensure_capture_running",
    "run_capture_serve",
]
