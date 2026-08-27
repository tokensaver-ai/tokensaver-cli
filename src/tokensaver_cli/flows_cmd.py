"""Flux IA deep links and recent pipeline runs."""

from __future__ import annotations

import sys
import webbrowser
from typing import Any

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.config import RouteConfigError, resolve_route_config
from tokensaver_cli.credentials import resolve_access_token
from tokensaver_cli.status import fetch_recent_flow_id


def _list_recent_runs(cfg, *, limit: int = 5) -> list[dict[str, Any]]:
    """List recent runs via SDK (API key). Fallback: monitoring + JWT."""
    # Primary: API-key surface used by Claude / MCP
    try:
        data = request_json(
            "GET",
            f"{cfg.api_v1_base}/sdk/runs?limit={limit}",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
        )
    except ApiError:
        data = None
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and items:
            out: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                rid = item.get("pipeline_run_id") or item.get("request_id") or item.get("id")
                if not rid:
                    continue
                out.append(
                    {
                        "id": str(rid),
                        "request_id": item.get("request_id"),
                        "model": item.get("model") or item.get("provider"),
                        "status": "cache" if item.get("cache_hit") else None,
                    }
                )
                if len(out) >= limit:
                    break
            if out:
                return out

    # Fallback: JWT monitoring list
    token = resolve_access_token()
    if not token:
        return []
    try:
        data = request_json(
            "GET",
            f"{cfg.api_v1_base}/monitoring/pipelines?days=7",
            headers={"Authorization": f"Bearer {token}"},
        )
    except ApiError:
        return []
    if not isinstance(data, dict):
        return []
    out = []
    for key in ("recent_runs", "recent_run_ids"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str) and item.strip():
                out.append({"id": item.strip()})
            elif isinstance(item, dict):
                out.append(item)
            if len(out) >= limit:
                return out
    return out[:limit]


def run_flows(
    *,
    force_local: bool = False,
    open_browser: bool = False,
    limit: int = 5,
) -> int:
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    flow_id = fetch_recent_flow_id(cfg)
    url = cfg.flows_url(flow_id=flow_id)
    print("TokenSaver Flux IA")
    print(f"  Console: {url}")
    if flow_id:
        print(f"  Latest:  {flow_id}")
    print()
    runs = _list_recent_runs(cfg, limit=limit)
    if runs:
        print(f"Recent runs (up to {limit}):")
        for row in runs:
            rid = row.get("id") or row.get("run_id") or "?"
            model = row.get("model") or ""
            extra = model or row.get("pipeline") or row.get("status") or ""
            suffix = f"  {extra}" if extra else ""
            print(f"  {rid}{suffix}")
        print()
    else:
        print("No recent runs found (send a Claude message first).")
        print()

    print("MCP: tokensaver_list_runs · tokensaver_get_last_run_detail · tokensaver_open_run_console")
    if open_browser:
        webbrowser.open(url)
        print("Opened browser.")
    return 0
