"""Resolved URLs and credentials for ``tokensaver route``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

PROD_API_HOST = "https://api.tokensaver.fr"
PROD_MCP_URL = "https://mcp.tokensaver.fr/mcp"
PROD_GATEWAY_URL = "https://gateway.tokensaver.fr/mcp"
PROD_CONSOLE_URL = "https://platform.tokensaver.fr"

LOCAL_API_HOST = "http://localhost:8000"
LOCAL_MCP_URL = "http://localhost:8787/mcp"
LOCAL_GATEWAY_URL = "http://localhost:8788/mcp"
LOCAL_EGRESS_PROXY = "http://127.0.0.1:8888"
LOCAL_CONSOLE_URL = "http://localhost:7337"

MCP_TOOLS_KEY = "tokensaver-route-tools"
MCP_GATEWAY_KEY = "tokensaver-route-gateway"
MCP_FS_KEY = "tokensaver-route-fs"

DeployMode = str  # "saas" | "local"
ClaudeScope = str  # "user" | "project" | "local"


def _strip_trailing_slash(url: str) -> str:
    return url.rstrip("/")


def _is_local_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _dotenv_get(path: "Path", key: str) -> str | None:
    """Read a single KEY=value from a dotenv file (no expansion)."""
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    prefix = f"{key}="
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        return value.strip() or None
    return None


def _console_url_from_port(port: str | None) -> str | None:
    if not port:
        return None
    digits = str(port).strip()
    if not digits.isdigit():
        return None
    return f"http://localhost:{int(digits)}"


def _monorepo_roots() -> list["Path"]:
    """Candidate TokenSaver monorepo roots (cwd walk + editable CLI install)."""
    from pathlib import Path

    seen: set[Path] = set()
    out: list[Path] = []

    def _add(p: Path) -> None:
        try:
            resolved = p.resolve()
        except OSError:
            return
        if resolved in seen:
            return
        seen.add(resolved)
        out.append(resolved)

    here = Path.cwd()
    for parent in [here, *here.parents]:
        _add(parent)
        if len(out) >= 12:
            break

    # packages/cli/src/tokensaver_cli/config.py → monorepo root = parents[4]
    try:
        pkg_file = Path(__file__).resolve()
        if pkg_file.parents[2].name == "cli" and pkg_file.parents[3].name == "packages":
            _add(pkg_file.parents[4])
    except (OSError, IndexError):
        pass

    return out


def discover_local_console_url() -> str | None:
    """Infer local console URL from monorepo ``.env`` / ``apps/console/.env.local``.

    Prefer ``CONSOLE_BASE_URL`` (backend) then ``PORT`` in the console dotenv.
    """
    from pathlib import Path

    for root in _monorepo_roots():
        console_env = root / "apps" / "console" / ".env.local"
        root_env = root / ".env"
        # Only treat as monorepo when console app or packages/cli is present.
        if not console_env.parent.is_dir() and not (root / "packages" / "cli").is_dir():
            continue

        base = _dotenv_get(root_env, "CONSOLE_BASE_URL")
        if base and _is_local_host(base):
            return _strip_trailing_slash(base)

        port = _dotenv_get(console_env, "PORT") or _dotenv_get(root_env, "PORT")
        from_port = _console_url_from_port(port)
        if from_port:
            return from_port

    return None


def resolve_local_console_url(*, sticky: str | None = None) -> str:
    """Local console URL for doctor / Flux IA deep links.

    Priority:
    1. ``TOKENSAVER_CONSOLE_URL`` (if localhost)
    2. ``CONSOLE_BASE_URL`` (if localhost) — same var as the backend
    3. Monorepo discovery (``apps/console/.env.local`` ``PORT=…``, root ``CONSOLE_BASE_URL``)
    4. Sticky credentials ``console_url`` (local)
    5. ``LOCAL_CONSOLE_URL`` (``http://localhost:7337``)
    """
    for key in ("TOKENSAVER_CONSOLE_URL", "CONSOLE_BASE_URL"):
        raw = _strip_trailing_slash(os.environ.get(key) or "")
        if raw and _is_local_host(raw):
            return raw

    discovered = discover_local_console_url()
    if discovered:
        return discovered

    sticky_url = _strip_trailing_slash(sticky or "")
    if sticky_url and _is_local_host(sticky_url):
        return sticky_url

    return LOCAL_CONSOLE_URL


def resolve_deploy_mode(*, api_host: str | None = None, force_local: bool = False) -> DeployMode:
    if force_local:
        return "local"
    # When a concrete host is already chosen (sticky login / flags), mode follows the host.
    # TOKENSAVER_MODE must not flip a SaaS sticky host back to "local".
    if api_host is not None:
        return "local" if _is_local_host(api_host) else "saas"

    explicit = (os.environ.get("TOKENSAVER_MODE") or "").strip().lower()
    if explicit in {"local", "self-host", "selfhost", "self_host"}:
        return "local"
    if explicit in {"saas", "cloud", "prod", "production"}:
        return "saas"

    host = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_API_URL")
        or os.environ.get("TOKENSAVER_API_BASE_URL")
        or PROD_API_HOST
    )
    if host.endswith("/api/v1"):
        host = host[: -len("/api/v1")]

    return "local" if _is_local_host(host) else "saas"


@dataclass(frozen=True)
class RouteConfig:
    api_key: str
    api_host: str
    anthropic_base_url: str
    openai_base_url: str
    mcp_tools_url: str
    gateway_url: str
    organisation_id: str | None
    workspace_id: str | None
    deploy_mode: DeployMode
    egress_proxy_url: str
    console_url: str

    @property
    def api_v1_base(self) -> str:
        host = _strip_trailing_slash(self.api_host)
        if host.endswith("/api/v1"):
            return host
        return f"{host}/api/v1"

    def flows_url(self, *, flow_id: str | None = None, locale: str = "fr") -> str:
        """Console Flux IA deep link: ``/{locale}/{workspaceId}/dashboard?tab=flows``."""
        base = _strip_trailing_slash(self.console_url)
        loc = (locale or "fr").strip() or "fr"
        ws = (self.workspace_id or "").strip()
        if ws:
            url = f"{base}/{loc}/{ws}/dashboard?tab=flows"
        else:
            # No workspace in credentials yet — locale-only fallback (login refreshes ws id).
            url = f"{base}/{loc}/dashboard?tab=flows"
        if flow_id and flow_id.strip():
            return f"{url}&flowId={flow_id.strip()}"
        return url


def resolve_route_config(*, force_local: bool = False) -> RouteConfig:
    from tokensaver_cli.credentials import load_credentials, resolve_api_key

    creds = load_credentials()
    api_key = resolve_api_key()
    if not api_key:
        raise RouteConfigError(
            "No credentials found. Run: tokensaver login\n"
            "(Session JWT only — backend maps it to your API key, like the console.)"
        )

    explicit = (os.environ.get("TOKENSAVER_MODE") or "").strip().lower()
    mode_wants_local = explicit in {"local", "self-host", "selfhost", "self_host"}

    env_host = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_API_URL") or os.environ.get("TOKENSAVER_API_BASE_URL") or ""
    )
    if env_host.endswith("/api/v1"):
        env_host = env_host[: -len("/api/v1")]

    # Priority:
    # 1) --local always wins
    # 2) sticky credentials.api_host from login (SaaS or local) — beats leftover
    #    TOKENSAVER_MODE=local / monorepo .env localhost so SaaS login sticks
    # 3) TOKENSAVER_MODE=local when no sticky host
    # 4) non-local TOKENSAVER_API_URL
    # 5) SaaS default
    if force_local:
        api_host = env_host or (
            creds.api_host if creds and creds.api_host and _is_local_host(creds.api_host) else None
        ) or LOCAL_API_HOST
    elif creds and creds.api_host:
        api_host = creds.api_host
    elif mode_wants_local:
        api_host = env_host or LOCAL_API_HOST
    elif env_host and not _is_local_host(env_host):
        api_host = env_host
    else:
        api_host = PROD_API_HOST

    deploy_mode = resolve_deploy_mode(api_host=api_host, force_local=force_local)

    anthropic_base = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_ANTHROPIC_BASE_URL") or f"{api_host}/anthropic"
    )
    openai_base = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_OPENAI_BASE_URL") or f"{api_host}/openai/v1"
    )

    def _pick_service_url(env_key: str, *, local_default: str, saas_default: str) -> str:
        raw = (os.environ.get(env_key) or "").strip()
        if not raw:
            return local_default if deploy_mode == "local" else saas_default
        # Ignore leftover localhost service URLs when running SaaS sticky login.
        if deploy_mode != "local" and _is_local_host(raw):
            return saas_default
        return raw

    mcp_url = _pick_service_url(
        "TOKENSAVER_MCP_URL", local_default=LOCAL_MCP_URL, saas_default=PROD_MCP_URL
    )
    gateway_url = _pick_service_url(
        "TOKENSAVER_GATEWAY_URL", local_default=LOCAL_GATEWAY_URL, saas_default=PROD_GATEWAY_URL
    )
    egress_proxy = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_EGRESS_PROXY") or LOCAL_EGRESS_PROXY
    )
    if deploy_mode == "local":
        sticky_console = creds.console_url if creds and creds.console_url else None
        console_url = resolve_local_console_url(sticky=sticky_console)
    else:
        default_console = PROD_CONSOLE_URL
        if creds and creds.console_url and not _is_local_host(creds.console_url):
            default_console = creds.console_url
        env_console = _strip_trailing_slash(os.environ.get("TOKENSAVER_CONSOLE_URL") or "")
        if env_console and not _is_local_host(env_console):
            console_url = env_console
        else:
            console_url = default_console

    org_id = (os.environ.get("X-Organisation-ID") or os.environ.get("X-Team-ID") or "").strip() or None
    workspace_id = (os.environ.get("X-Workspace-ID") or "").strip() or None
    if not org_id and creds and creds.organisation_id:
        org_id = creds.organisation_id
    if not workspace_id and creds and creds.workspace_id:
        workspace_id = creds.workspace_id

    return RouteConfig(
        api_key=api_key,
        api_host=api_host,
        anthropic_base_url=anthropic_base,
        openai_base_url=openai_base,
        mcp_tools_url=mcp_url,
        gateway_url=gateway_url,
        organisation_id=org_id,
        workspace_id=workspace_id,
        deploy_mode=deploy_mode,
        egress_proxy_url=egress_proxy,
        console_url=console_url,
    )


class RouteConfigError(Exception):
    """Missing or invalid route configuration."""
