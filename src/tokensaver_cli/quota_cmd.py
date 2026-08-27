"""Fast local quota / usage dashboard (single SDK round-trip)."""

from __future__ import annotations

import sys
from typing import Any

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.auth_cmd import _api_host, _api_v1, _console_url
from tokensaver_cli.config import RouteConfigError, resolve_route_config
from tokensaver_cli.credentials import load_credentials, resolve_api_key


def _fmt_num(value: Any) -> str:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return "—"
    return f"{n:,}".replace(",", " ")


def _fmt_usd(value: Any) -> str:
    try:
        return f"${float(value):.4f}"
    except (TypeError, ValueError):
        return "—"


def _bar(used: float, limit: float, width: int = 16) -> str:
    if limit <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, used / limit))
    filled = int(round(ratio * width))
    return "█" * filled + "░" * (width - filled)


def _print_consumption_block(title: str, summary: dict[str, Any] | None) -> None:
    s = summary if isinstance(summary, dict) else {}
    print(f"  {title}")
    print(f"    tokens   {_fmt_num(s.get('tokens_total'))}")
    print(f"    cost     {_fmt_usd(s.get('cost_usd'))}")
    print(f"    requests {_fmt_num(s.get('pipeline_requests'))}")


def run_quota(*, force_local: bool = False, full: bool = False) -> int:
    """Print quotas + usage from ``GET /sdk/me`` (and optional ``/sdk/quota-status``)."""
    try:
        cfg = resolve_route_config(force_local=force_local)
        api_v1 = cfg.api_v1_base
        key = cfg.api_key
        console = cfg.console_url
    except RouteConfigError:
        key = resolve_api_key()
        if not key:
            print("Not logged in. Run: tokensaver login", file=sys.stderr)
            return 1
        creds = load_credentials()
        host = (creds.api_host if creds and creds.api_host else None) or _api_host(
            force_local=force_local
        )
        api_v1 = _api_v1(host)
        console = (creds.console_url if creds and creds.console_url else None) or _console_url(
            force_local=force_local, api_host=host
        )

    headers = {"Authorization": f"Bearer {key}"}
    try:
        me = request_json("GET", f"{api_v1}/sdk/me", headers=headers, timeout=12.0)
    except ApiError as exc:
        print(f"FAIL  /sdk/me — {exc}", file=sys.stderr)
        return 1

    if not isinstance(me, dict):
        print("FAIL  unexpected /sdk/me payload", file=sys.stderr)
        return 1

    api_key = me.get("api_key") if isinstance(me.get("api_key"), dict) else {}
    plan = me.get("plan") if isinstance(me.get("plan"), dict) else {}
    usage = me.get("usage") if isinstance(me.get("usage"), dict) else {}
    consumption = me.get("consumption") if isinstance(me.get("consumption"), dict) else {}
    workspace = me.get("workspace") if isinstance(me.get("workspace"), dict) else {}

    print("TokenSaver · quotas & usage")
    print(f"  Key:   {api_key.get('name') or '—'}  ({api_key.get('prefix') or '—'}…)")
    print(f"  Plan:  {plan.get('name') or plan.get('slug') or '—'}")
    ws_id = workspace.get("id")
    if ws_id:
        print(f"  Flux:  {console.rstrip('/')}/fr/{ws_id}/dashboard?tab=flows")
    print()
    _print_consumption_block("Today (UTC)", consumption.get("today") if isinstance(consumption.get("today"), dict) else None)
    print()
    _print_consumption_block("Month", consumption.get("month") if isinstance(consumption.get("month"), dict) else None)

    quotas = plan.get("quotas") if isinstance(plan.get("quotas"), dict) else {}
    rows: list[tuple[str, float, float | None]] = []
    if quotas.get("tokens_per_month") is not None:
        rows.append(
            (
                "tokens/month",
                float(usage.get("tokens_used") or 0),
                float(quotas["tokens_per_month"]),
            )
        )
    if quotas.get("requests_per_month") is not None:
        rows.append(
            (
                "requests/month",
                float(usage.get("requests_used") or 0),
                float(quotas["requests_per_month"]),
            )
        )

    if rows:
        print()
        print("  Plan quotas")
        for label, used, limit in rows:
            if limit is None or limit <= 0:
                print(f"    {label}: {_fmt_num(used)} / ∞")
                continue
            pct = (used / limit) * 100.0
            print(f"    {label}: {_bar(used, limit)}  {_fmt_num(used)} / {_fmt_num(limit)}  ({pct:.0f}%)")

    if full:
        try:
            status = request_json(
                "GET", f"{api_v1}/sdk/quota-status", headers=headers, timeout=12.0
            )
        except ApiError as exc:
            print(f"\n  WARN  quota-status unavailable ({exc})", file=sys.stderr)
            return 0
        if isinstance(status, dict):
            print()
            print(f"  Overall: {status.get('overall_status') or '—'}")
            dims = status.get("dimensions")
            if isinstance(dims, list):
                for dim in dims:
                    if not isinstance(dim, dict):
                        continue
                    name = dim.get("label") or dim.get("name") or dim.get("key") or "—"
                    used = dim.get("used")
                    limit = dim.get("limit")
                    st = dim.get("status") or ""
                    print(f"    · {name}: {_fmt_num(used)} / {_fmt_num(limit)}  [{st}]")

    print()
    print("  Tip: tokensaver quota --full   # dimensions détaillées")
    return 0
