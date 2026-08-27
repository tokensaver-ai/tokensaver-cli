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
LOCAL_CONSOLE_URL = "http://localhost:3000"

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


def resolve_deploy_mode(*, api_host: str | None = None, force_local: bool = False) -> DeployMode:
    if force_local:
        return "local"
    explicit = (os.environ.get("TOKENSAVER_MODE") or "").strip().lower()
    if explicit in {"local", "self-host", "selfhost", "self_host"}:
        return "local"
    if explicit in {"saas", "cloud", "prod", "production"}:
        return "saas"

    host = api_host
    if host is None:
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

    deploy_mode = resolve_deploy_mode(force_local=force_local)
    default_api_host = LOCAL_API_HOST if deploy_mode == "local" else PROD_API_HOST
    if creds and creds.api_host and not (
        os.environ.get("TOKENSAVER_API_URL") or os.environ.get("TOKENSAVER_API_BASE_URL")
    ):
        default_api_host = creds.api_host

    api_host = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_API_URL") or os.environ.get("TOKENSAVER_API_BASE_URL") or default_api_host
    )
    if api_host.endswith("/api/v1"):
        api_host = api_host[: -len("/api/v1")]

    deploy_mode = resolve_deploy_mode(api_host=api_host, force_local=force_local)

    anthropic_base = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_ANTHROPIC_BASE_URL") or f"{api_host}/anthropic"
    )
    openai_base = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_OPENAI_BASE_URL") or f"{api_host}/openai/v1"
    )
    mcp_url = os.environ.get("TOKENSAVER_MCP_URL") or (
        LOCAL_MCP_URL if deploy_mode == "local" else PROD_MCP_URL
    )
    gateway_url = os.environ.get("TOKENSAVER_GATEWAY_URL") or (
        LOCAL_GATEWAY_URL if deploy_mode == "local" else PROD_GATEWAY_URL
    )
    egress_proxy = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_EGRESS_PROXY") or LOCAL_EGRESS_PROXY
    )
    default_console = LOCAL_CONSOLE_URL if deploy_mode == "local" else PROD_CONSOLE_URL
    if creds and creds.console_url and not os.environ.get("TOKENSAVER_CONSOLE_URL"):
        default_console = creds.console_url
    console_url = _strip_trailing_slash(
        os.environ.get("TOKENSAVER_CONSOLE_URL") or default_console
    )

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
