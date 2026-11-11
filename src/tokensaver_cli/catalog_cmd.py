"""Agent Registry helpers from the CLI."""

from __future__ import annotations

import sys
from typing import Any
from urllib.parse import quote

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.approve_cmd import _api_base, _auth_headers, approve_catalog_ref
from tokensaver_cli.credentials import resolve_access_token


def _list_assets(
    api_v1: str,
    *,
    status: str | None = None,
    asset_type: str = "model",
    q: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params = [f"type={quote(asset_type)}", f"limit={limit}"]
    if status:
        params.append(f"status={quote(status)}")
    if q:
        params.append(f"q={quote(q)}")
    qs = "&".join(params)
    headers = _auth_headers()
    try:
        data = request_json("GET", f"{api_v1}/sdk/catalog/assets?{qs}", headers=headers)
    except ApiError:
        token = resolve_access_token()
        if not token:
            raise
        data = request_json(
            "GET",
            f"{api_v1}/catalog/assets?{qs}",
            headers={"Authorization": f"Bearer {token}"},
        )
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict)]


def run_catalog(
    action: str | None = None,
    ref: str | None = None,
    *,
    force_local: bool = False,
    status: str | None = None,
) -> int:
    act = (action or "list").strip().lower()
    api_v1 = _api_base(force_local=force_local)

    if act in ("approve", "allow"):
        target = (ref or "").strip()
        if not target:
            print("Usage: tokensaver catalog approve <provider/model>", file=sys.stderr)
            return 2
        try:
            asset = approve_catalog_ref(target, force_local=force_local)
        except ApiError as exc:
            print(f"FAIL  {exc}", file=sys.stderr)
            return 1
        print(f"OK  approved {asset.get('ref')}  status={asset.get('status')}")
        return 0

    if act not in ("list", "pending", "ls"):
        print("Usage: tokensaver catalog [list|pending|approve <ref>]", file=sys.stderr)
        return 2

    filter_status = status
    if act == "pending" and not filter_status:
        # show both pending buckets
        rows: list[dict[str, Any]] = []
        for st in ("quarantined", "discovered"):
            try:
                rows.extend(_list_assets(api_v1, status=st, asset_type="model"))
            except ApiError as exc:
                print(f"FAIL  list catalog — {exc}", file=sys.stderr)
                return 1
        # de-dupe by id
        seen: set[str] = set()
        uniq: list[dict[str, Any]] = []
        for row in rows:
            aid = str(row.get("id") or "")
            if aid and aid in seen:
                continue
            if aid:
                seen.add(aid)
            uniq.append(row)
        rows = uniq
    else:
        try:
            rows = _list_assets(api_v1, status=filter_status, asset_type="model")
        except ApiError as exc:
            print(f"FAIL  list catalog — {exc}", file=sys.stderr)
            return 1

    print("Agent Registry (models)")
    if not rows:
        print("  (empty)")
        return 0
    print(f"  {'STATUS':12}  REF")
    for row in rows:
        st = str(row.get("status") or "?")[:12]
        ref_s = row.get("ref") or "?"
        print(f"  {st:12}  {ref_s}")
    print()
    print("Approve: tokensaver catalog approve <ref>")
    print("     or: tokensaver approve <ref>")
    return 0
