"""tests for tokensaver flows run listing."""

from __future__ import annotations

from tokensaver_cli.config import RouteConfig
from tokensaver_cli.flows_cmd import _list_recent_runs


def test_list_recent_runs_uses_sdk_items() -> None:
    cfg = RouteConfig(
        api_key="ts_x",
        api_host="https://api.example.test",
        anthropic_base_url="https://api.example.test/anthropic",
        openai_base_url="https://api.example.test/openai/v1",
        mcp_tools_url="https://mcp.example.test/mcp",
        gateway_url="https://gateway.example.test/mcp",
        organisation_id=None,
        workspace_id="ws-1",
        deploy_mode="saas",
        egress_proxy_url="http://127.0.0.1:8888",
        console_url="https://platform.example.test",
    )

    def fake_request(method, url, *, headers=None, body=None, timeout=30.0):
        assert "/sdk/runs" in url
        return {
            "items": [
                {
                    "pipeline_run_id": "run-1",
                    "request_id": "req-1",
                    "model": "openrouter/z-ai/glm-4.7-flash",
                }
            ]
        }

    import tokensaver_cli.flows_cmd as mod

    orig = mod.request_json
    mod.request_json = fake_request  # type: ignore[assignment]
    try:
        rows = _list_recent_runs(cfg, limit=5)
    finally:
        mod.request_json = orig  # type: ignore[assignment]
    assert rows[0]["id"] == "run-1"
    assert "glm" in str(rows[0].get("model"))
