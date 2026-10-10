"""Tests for CLI argument parsing."""

from __future__ import annotations

from tokensaver_cli.main import _parse_route_tail, _split_passthrough, build_parser


def test_parse_route_tail_strips_launch_from_agent_args() -> None:
    launch, extra, extras = _parse_route_tail(launch_flag=False, remainder=["--launch"])
    assert launch is True
    assert extra == []
    assert extras == {}


def test_parse_route_tail_keeps_launch_flag() -> None:
    launch, extra, extras = _parse_route_tail(launch_flag=True, remainder=[])
    assert launch is True
    assert extra == []
    assert extras == {}


def test_split_passthrough_forwards_args_after_double_dash() -> None:
    main_argv, passthrough = _split_passthrough(
        ["route", "claude", "--launch", "--", "--model", "anthropic/claude-sonnet-4-6"]
    )
    assert main_argv == ["route", "claude", "--launch"]
    assert passthrough == ["--model", "anthropic/claude-sonnet-4-6"]


def test_parse_route_tail_extra_args() -> None:
    launch, extra, extras = _parse_route_tail(launch_flag=False, remainder=["--verbose"])
    assert launch is False
    assert extra == ["--verbose"]
    assert extras == {}


def test_parse_route_tail_claude_flags_after_target() -> None:
    launch, extra, extras = _parse_route_tail(
        launch_flag=False,
        remainder=["--scope", "project", "--profile", "cheap", "--with-fs", "--local"],
    )
    assert launch is False
    assert extra == []
    assert extras["scope"] == "project"
    assert extras["profile"] == "cheap"
    assert extras["with_fs"] is True
    assert extras["local"] is True


def test_status_line_flag_parsed() -> None:
    args, unknown = build_parser().parse_known_args(["status", "--line"])
    assert args.command == "status"
    assert args.line is True
    assert unknown == []
