"""Business loops (ACP-9): tokensaver loop start | tick | end | status | precheck | env."""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.config import RouteConfig, RouteConfigError, resolve_route_config
from tokensaver_cli.project_stamp import project_attrs

LOOP_KINDS = (
    "turn_based",
    "goal_based",
    "time_based",
    "proactive",
    "tool_linked",
    "custom_sco",
)

ENV_LOOP_ID = "TOKENSAVER_LOOP_ID"
ENV_LOOP_KIND = "TOKENSAVER_LOOP_KIND"
ENV_LOOP_ITERATION = "TOKENSAVER_LOOP_ITERATION"


def _auth_headers(cfg: RouteConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.api_key}"}


def _loops_base(cfg: RouteConfig) -> str:
    return f"{cfg.api_v1_base}/loops"


def _execution_graph_url(cfg: RouteConfig, *, loop_id: str | None = None, locale: str = "fr") -> str:
    base = cfg.console_url.rstrip("/")
    loc = (locale or "fr").strip() or "fr"
    ws = (cfg.workspace_id or "").strip()
    path = f"{base}/{loc}/{ws}/execution-graph" if ws else f"{base}/{loc}/execution-graph"
    q = "mode=loops"
    if loop_id:
        q += f"&loopId={loop_id}"
    return f"{path}?{q}"


def _current_loop_id(explicit: str | None = None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    try:
        from tokensaver_cli.egress_bridge import apply_egress_bridge

        apply_egress_bridge(only_if_unset=True)
    except Exception:
        pass
    return (os.environ.get(ENV_LOOP_ID) or "").strip() or None


def _current_kind(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return (os.environ.get(ENV_LOOP_KIND) or "goal_based").strip() or "goal_based"


def _current_iteration(explicit: int | None = None) -> int:
    if explicit is not None:
        return max(1, int(explicit))
    raw = (os.environ.get(ENV_LOOP_ITERATION) or "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _print_exports(*, loop_id: str, loop_kind: str, iteration: int) -> None:
    # Safe for eval "$(tokensaver loop start --export)"
    def sh(s: str) -> str:
        return "'" + s.replace("'", "'\"'\"'") + "'"

    print(f"export {ENV_LOOP_ID}={sh(loop_id)}")
    print(f"export {ENV_LOOP_KIND}={sh(loop_kind)}")
    print(f"export {ENV_LOOP_ITERATION}={sh(str(iteration))}")


def _print_human_start(cfg: RouteConfig, row: dict[str, Any], *, iteration: int) -> None:
    loop_id = str(row.get("loop_id") or "")
    kind = str(row.get("loop_kind") or "")
    status = str(row.get("status") or "")
    print("TokenSaver business loop started (ACP-9)")
    print(f"  loop_id:  {loop_id}")
    print(f"  kind:     {kind}")
    print(f"  status:   {status}")
    print(f"  iter:     {iteration}")
    print()
    print("Export for egress / child processes:")
    print(f"  export {ENV_LOOP_ID}={loop_id}")
    print(f"  export {ENV_LOOP_KIND}={kind}")
    print(f"  export {ENV_LOOP_ITERATION}={iteration}")
    print(f"  # optional: export TOKENSAVER_LOOP_PRECHECK=1")
    print()
    print(f"  Or: eval \"$(tokensaver loop start … --export)\"  # after start, use: tokensaver loop env")
    print()
    print(f"Boucles:  {_execution_graph_url(cfg, loop_id=loop_id)}")
    print(f"Flux IA:  {cfg.flows_url()}")


def run_loop_start(
    *,
    force_local: bool = False,
    kind: str = "goal_based",
    goal: str | None = None,
    max_turns: int | None = None,
    budget_usd: float | None = None,
    loop_id: str | None = None,
    export: bool = False,
    agent_id: str | None = None,
) -> int:
    if kind not in LOOP_KINDS:
        print(f"Invalid --kind {kind!r}. Choose: {', '.join(LOOP_KINDS)}", file=sys.stderr)
        return 1
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    lid = (loop_id or "").strip() or f"loop_{uuid.uuid4().hex[:24]}"
    goal_obj: dict[str, Any] | None = None
    if goal or max_turns:
        goal_obj = {}
        if goal:
            goal_obj["expression"] = goal
        if max_turns is not None:
            goal_obj["max_turns"] = max_turns
    budgets: dict[str, Any] | None = None
    if budget_usd is not None:
        budgets = {"max_cost_usd": budget_usd}
    if max_turns is not None:
        budgets = {**(budgets or {}), "max_iterations": max_turns}

    body: dict[str, Any] = {
        "loop_id": lid,
        "loop_kind": kind,
        "status": "running",
        "attrs": project_attrs(),
        "trigger": {"type": "cli", "source": "tokensaver_cli"},
    }
    if agent_id:
        body["agent_id"] = agent_id
    if goal_obj:
        body["goal"] = goal_obj
    if budgets:
        body["budgets"] = budgets

    try:
        row = request_json(
            "POST",
            _loops_base(cfg),
            headers=_auth_headers(cfg),
            body=body,
        )
        # Emit start event so iterations / UI have a lifecycle anchor
        request_json(
            "POST",
            f"{_loops_base(cfg)}/events",
            headers=_auth_headers(cfg),
            body={
                "event": "start",
                "loop_id": lid,
                "loop_kind": kind,
                "decision": "continue",
                "goal": goal_obj,
                "budgets": budgets,
                "attrs": project_attrs(),
            },
        )
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not isinstance(row, dict):
        print("Unexpected API response", file=sys.stderr)
        return 1

    iteration = 1
    if export:
        _print_exports(loop_id=str(row.get("loop_id") or lid), loop_kind=kind, iteration=iteration)
        return 0
    _print_human_start(cfg, row, iteration=iteration)
    return 0


def run_loop_env(*, force_local: bool = False) -> int:
    """Print export lines for the current env loop (or error)."""
    lid = _current_loop_id()
    if not lid:
        print(f"No {ENV_LOOP_ID} in environment. Run: tokensaver loop start", file=sys.stderr)
        return 1
    _print_exports(
        loop_id=lid,
        loop_kind=_current_kind(),
        iteration=_current_iteration(),
    )
    return 0


def run_loop_tick(
    *,
    force_local: bool = False,
    loop_id: str | None = None,
    iteration: int | None = None,
    export: bool = False,
) -> int:
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    lid = _current_loop_id(loop_id)
    if not lid:
        print(f"Missing loop id. Pass --loop-id or set {ENV_LOOP_ID}.", file=sys.stderr)
        return 1
    kind = _current_kind()
    if iteration is not None:
        nxt = max(1, int(iteration))
    else:
        env_i = (os.environ.get(ENV_LOOP_ITERATION) or "").strip()
        nxt = int(env_i) + 1 if env_i.isdigit() else 1

    try:
        request_json(
            "POST",
            f"{_loops_base(cfg)}/events",
            headers=_auth_headers(cfg),
            body={
                "event": "iteration",
                "loop_id": lid,
                "loop_kind": kind,
                "iteration_index": nxt,
                "decision": "continue",
            },
        )
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if export:
        _print_exports(loop_id=lid, loop_kind=kind, iteration=nxt)
        return 0
    print(f"Loop iteration recorded: {lid} · iter {nxt}")
    print(f"  export {ENV_LOOP_ITERATION}={nxt}")
    print(f"Boucles: {_execution_graph_url(cfg, loop_id=lid)}")
    return 0


def run_loop_end(
    *,
    force_local: bool = False,
    loop_id: str | None = None,
    reason: str = "work_complete",
) -> int:
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    lid = _current_loop_id(loop_id)
    if not lid:
        print(f"Missing loop id. Pass --loop-id or set {ENV_LOOP_ID}.", file=sys.stderr)
        return 1
    kind = _current_kind()
    try:
        request_json(
            "POST",
            f"{_loops_base(cfg)}/events",
            headers=_auth_headers(cfg),
            body={
                "event": "end",
                "loop_id": lid,
                "loop_kind": kind,
                "decision": "stop",
                "stop_reason": reason,
            },
        )
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Loop ended: {lid} · reason={reason}")
    print(f"Boucles: {_execution_graph_url(cfg, loop_id=lid)}")
    return 0


def run_loop_status(
    *,
    force_local: bool = False,
    loop_id: str | None = None,
    as_json: bool = False,
) -> int:
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    lid = _current_loop_id(loop_id)
    if not lid:
        # List recent loops
        try:
            data = request_json(
                "GET",
                f"{_loops_base(cfg)}?limit=10",
                headers=_auth_headers(cfg),
            )
        except ApiError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        items = data.get("items") if isinstance(data, dict) else None
        if as_json:
            print(json.dumps(data if isinstance(data, dict) else {"items": []}, indent=2))
            return 0
        print("Recent business loops (pass --loop-id or set TOKENSAVER_LOOP_ID for detail):")
        if not isinstance(items, list) or not items:
            print("  (none)")
            return 0
        for row in items[:10]:
            if not isinstance(row, dict):
                continue
            print(
                f"  {row.get('loop_id')}  {row.get('loop_kind')}  {row.get('status')}  "
                f"iters={row.get('iteration_count')}"
            )
        print(f"\nBoucles: {_execution_graph_url(cfg)}")
        return 0

    try:
        data = request_json(
            "GET",
            f"{_loops_base(cfg)}/{lid}",
            headers=_auth_headers(cfg),
        )
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(data, indent=2))
        return 0
    if not isinstance(data, dict):
        print("Unexpected response", file=sys.stderr)
        return 1
    print(f"loop_id:  {data.get('loop_id')}")
    print(f"kind:     {data.get('loop_kind')}")
    print(f"status:   {data.get('status')}")
    print(f"stop:     {data.get('stop_reason')}")
    print(f"iters:    {data.get('iteration_count')}")
    print(f"tokens:   {data.get('total_tokens')}")
    print(f"cost_usd: {data.get('total_cost_usd')}")
    print(f"Boucles:  {_execution_graph_url(cfg, loop_id=str(data.get('loop_id') or lid))}")
    return 0


def run_loop_precheck(
    *,
    force_local: bool = False,
    loop_id: str | None = None,
    next_iteration: int | None = None,
) -> int:
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    lid = _current_loop_id(loop_id)
    if not lid:
        print(f"Missing loop id. Pass --loop-id or set {ENV_LOOP_ID}.", file=sys.stderr)
        return 1
    body: dict[str, Any] = {}
    if next_iteration is not None:
        body["next_iteration"] = next_iteration
    try:
        data = request_json(
            "POST",
            f"{_loops_base(cfg)}/{lid}/precheck",
            headers=_auth_headers(cfg),
            body=body or None,
        )
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2) if isinstance(data, dict) else data)
    return 0


def run_loop(argv_action: str | None, *, force_local: bool = False, extras: dict | None = None) -> int:
    """Dispatch ``tokensaver loop <action>``."""
    extras = extras or {}
    action = (argv_action or "status").strip().lower()
    export = bool(extras.get("export"))
    as_json = bool(extras.get("json"))
    kind = extras.get("kind") or "goal_based"
    goal = extras.get("goal")
    max_turns = extras.get("max_turns")
    budget_usd = extras.get("budget_usd")
    loop_id = extras.get("loop_id")
    reason = extras.get("reason") or "work_complete"
    iteration = extras.get("iteration")
    agent_id = extras.get("agent_id")

    if action in ("start", "create"):
        return run_loop_start(
            force_local=force_local,
            kind=str(kind),
            goal=goal,
            max_turns=int(max_turns) if max_turns is not None else None,
            budget_usd=float(budget_usd) if budget_usd is not None else None,
            loop_id=loop_id,
            export=export,
            agent_id=agent_id,
        )
    if action == "tick":
        return run_loop_tick(
            force_local=force_local,
            loop_id=loop_id,
            iteration=int(iteration) if iteration is not None else None,
            export=export,
        )
    if action == "end":
        return run_loop_end(force_local=force_local, loop_id=loop_id, reason=str(reason))
    if action in ("status", "get", "list"):
        return run_loop_status(force_local=force_local, loop_id=loop_id, as_json=as_json)
    if action == "precheck":
        return run_loop_precheck(
            force_local=force_local,
            loop_id=loop_id,
            next_iteration=int(iteration) if iteration is not None else None,
        )
    if action == "env":
        return run_loop_env(force_local=force_local)
    print(
        "Usage: tokensaver loop start|tick|end|status|precheck|env "
        "[--kind …] [--goal …] [--max-turns N] [--export] [--local]",
        file=sys.stderr,
    )
    return 1
