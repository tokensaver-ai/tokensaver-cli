"""Persist route state and config backups for ``unroute``."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:  # Python < 3.11
    UTC = timezone.utc
from pathlib import Path
from typing import Any


@dataclass
class RoutedFile:
    path: str
    backup: str


@dataclass
class RouteRecord:
    target: str
    routed_at: str
    files: list[RoutedFile]
    meta: dict[str, Any] = field(default_factory=dict)


def route_state_dir() -> Path:
    base = Path.home() / ".config" / "tokensaver" / "route"
    base.mkdir(parents=True, exist_ok=True)
    return base


def backups_dir() -> Path:
    path = route_state_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_file() -> Path:
    return route_state_dir() / "state.json"


def load_state() -> dict[str, RouteRecord]:
    path = state_file()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, RouteRecord] = {}
    for target, rec in (raw.get("routes") or {}).items():
        files = [RoutedFile(**f) for f in rec.get("files") or []]
        meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
        out[target] = RouteRecord(
            target=target,
            routed_at=rec.get("routed_at", ""),
            files=files,
            meta=meta,
        )
    return out


def save_state(routes: dict[str, RouteRecord]) -> None:
    payload = {
        "routes": {
            target: {
                "target": rec.target,
                "routed_at": rec.routed_at,
                "files": [asdict(f) for f in rec.files],
                "meta": rec.meta,
            }
            for target, rec in routes.items()
        }
    }
    state_file().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def backup_file(source: Path) -> str | None:
    if not source.is_file():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = backups_dir() / f"{source.name}.{stamp}.bak"
    shutil.copy2(source, dest)
    return str(dest)


def restore_file(source: Path, backup_path: str) -> None:
    backup = Path(backup_path)
    if not backup.is_file():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, source)


def record_route(
    target: str,
    files: list[RoutedFile],
    *,
    meta: dict[str, Any] | None = None,
) -> None:
    routes = load_state()
    routes[target] = RouteRecord(
        target=target,
        routed_at=datetime.now(UTC).isoformat(),
        files=files,
        meta=dict(meta or {}),
    )
    save_state(routes)


def clear_route(target: str) -> RouteRecord | None:
    routes = load_state()
    rec = routes.pop(target, None)
    save_state(routes)
    return rec
