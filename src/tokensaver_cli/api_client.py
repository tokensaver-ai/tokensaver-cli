"""Minimal HTTP JSON client for TokenSaver API (stdlib only)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


class ApiError(Exception):
    def __init__(self, status: int, detail: Any, *, url: str = ""):
        self.status = status
        self.detail = detail
        self.url = url
        super().__init__(self._format())

    def _format(self) -> str:
        detail = self.detail
        if isinstance(detail, dict):
            msg = detail.get("message") or detail.get("detail") or detail.get("error_code")
            if isinstance(msg, dict):
                msg = msg.get("message") or msg.get("error_code") or str(msg)
            if msg is None and "detail" in detail:
                msg = detail["detail"]
            text = str(msg) if msg is not None else json.dumps(detail)[:300]
        else:
            text = str(detail)[:300]
        return f"HTTP {self.status}: {text}"


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method.upper(), headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw) if raw.strip() else {"detail": raw}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:500]}
        raise ApiError(exc.code, parsed, url=url) from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise ApiError(
                0,
                f"Request timed out after {timeout}s — API unreachable at {url}. "
                "Check api.tokensaver.fr status, your network/VPN, or use "
                "`tokensaver login --local` / `tokensaver login --key ts_…`.",
                url=url,
            ) from exc
        raise ApiError(0, f"Connection failed: {reason}", url=url) from exc
    except TimeoutError as exc:
        raise ApiError(
            0,
            f"Request timed out after {timeout}s — API unreachable at {url}.",
            url=url,
        ) from exc
