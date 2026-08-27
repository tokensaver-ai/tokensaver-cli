"""CLI entrypoint: tokensaver route | login | keys | doctor | …"""

from __future__ import annotations

import argparse
import sys

from tokensaver_cli.agents import (
    route_claude,
    route_codex,
    route_cursor,
    route_mcp,
    route_proxy,
    unroute_claude,
    unroute_codex,
    unroute_cursor,
    unroute_mcp,
    unroute_proxy,
)
from tokensaver_cli.approve_cmd import run_approve
from tokensaver_cli.auth_cmd import run_login, run_logout, run_resend_verification, run_verify_email, run_whoami
from tokensaver_cli.banner import print_banner
from tokensaver_cli.catalog_cmd import run_catalog
from tokensaver_cli.config import RouteConfigError, resolve_route_config
from tokensaver_cli.doctor import run_doctor
from tokensaver_cli.flows_cmd import run_flows
from tokensaver_cli.keys_cmd import run_keys_create, run_keys_list, run_keys_revoke
from tokensaver_cli.models_cmd import run_models
from tokensaver_cli.profiles import profiles_summary
from tokensaver_cli.status import run_status
from tokensaver_cli.use_cmd import run_use

ROUTE_TARGETS = ("claude", "cursor", "codex", "proxy", "mcp")
UNROUTE_TARGETS = ("claude", "cursor", "codex", "proxy", "mcp")
COMMANDS = (
    "route",
    "unroute",
    "doctor",
    "status",
    "profiles",
    "models",
    "use",
    "flows",
    "catalog",
    "login",
    "logout",
    "whoami",
    "verify-email",
    "resend-verification",
    "keys",
    "approve",
    "help",
)
KEYS_ACTIONS = ("list", "create", "revoke")
CATALOG_ACTIONS = ("list", "pending", "approve", "ls", "allow")

DOCS_URL = "https://github.com/tokensaver-ai/tokensaver-cli/tree/main/docs"
GITHUB_URL = "https://github.com/tokensaver-ai/tokensaver-cli"


def print_usage() -> None:
    print(
        f"""TokenSaver CLI — route agent traffic through the control plane

Usage:
  tokensaver login [--email …] [--signup|--key ts_…] [--local]
  tokensaver logout | whoami [--local]
  tokensaver verify-email <token-or-url>
  tokensaver resend-verification
  tokensaver keys list | create [--name …] [--use] | revoke <id>
  tokensaver approve [<provider/model>] [--current] [--quiet]
  tokensaver models [--local]
  tokensaver use <cheap|default|strong|provider/model> [--local]
  tokensaver flows [--open] [--local]
  tokensaver catalog [list|pending|approve <ref>] [--local]
  tokensaver route <target> [options] [-- extra-args...]
  tokensaver unroute <target>
  tokensaver doctor [--claude] [--local]
  tokensaver status [--line|--hook|--session-start]
  tokensaver profiles

Auth (no UI required):
  login     Create Free account or sign in → session JWT only (backend maps to API key)
  logout    Remove local credentials
  whoami    Show email, plan, verification status
  verify-email  Confirm inbox from email link (CLI-only, no console)
  resend-verification  Resend verification email (needs login JWT)
  keys      List / create / revoke TokenSaver API keys (needs login JWT; secrets not stored)
  approve   Agent Registry: approve a model (unblocks zero-trust 403)
  models    List profiles + catalogue models for your plan
  use       Set Claude model/profile (sticky) + approve
  flows     Flux IA URL + recent runs
  catalog   List / approve Agent Registry models

Route targets:
  claude    Claude Code — settings + MCP (+ optional launch / plugin)
  cursor    Cursor — writes .cursor/mcp.json + prints Override URL steps
  codex     OpenAI Codex — prints env vars (+ optional launch)
  proxy     Print OpenAI/Anthropic base URLs for any compatible client
  mcp       MCP Trust Gateway — SaaS URL or local stdio wrapper

Options (login):
  --email EMAIL         Account email
  --password PASS       Password (prefer prompt / env)
  --name NAME           Display name (signup)
  --org NAME            Organisation name (signup)
  --workspace NAME      Workspace name (signup)
  --signup              Force account creation
  --key ts_…            CI escape hatch: import ts_… (login normally uses JWT only)
  --local               Local API (http://localhost:8000)
  -y, --yes             Less interactive signup

Options (keys create):
  --name NAME           Key label (default CLI)
  --description TEXT    Optional description
  --use                 Save new key as default in credentials

Options (route claude):
  --launch --scope --model --profile --with-fs --no-plugin --local

Examples:
  tokensaver login
  tokensaver login --email you@acme.com --signup -y
  tokensaver route claude --launch
  tokensaver keys create --name Claude --use
  tokensaver doctor --claude

Install: pip install tokensaver-cli
Docs:    {DOCS_URL}
GitHub:  {GITHUB_URL}
"""
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tokensaver",
        description="Route AI agents through TokenSaver (cache, compression, PII, governance).",
        add_help=False,
    )
    parser.add_argument("command", nargs="?", choices=COMMANDS)
    parser.add_argument("target", nargs="?")
    parser.add_argument("arg", nargs="?", help="Extra arg (e.g. keys revoke <id>)")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--target", dest="mcp_target", default=None)
    parser.add_argument("--scope", choices=("user", "project", "local"), default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--with-fs", action="store_true")
    parser.add_argument("--no-plugin", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--line", action="store_true")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--session-start", action="store_true", help="Claude SessionStart hook (banner + context)")
    parser.add_argument("--welcome-json", action="store_true", help=argparse.SUPPRESS)
    # Auth / keys
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("--org", default=None)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--signup", action="store_true")
    parser.add_argument("--key", default=None, help="Import existing ts_… API key")
    parser.add_argument("--description", default=None)
    parser.add_argument("--use", action="store_true", help="keys create: set as default")
    parser.add_argument(
        "--current",
        action="store_true",
        help="approve: use ANTHROPIC_MODEL / Claude settings model",
    )
    parser.add_argument("--quiet", action="store_true", help="approve: compact output")
    parser.add_argument("--type", dest="asset_type", default="model", help="approve asset type")
    parser.add_argument("--open", action="store_true", help="flows: open Flux IA in browser")
    parser.add_argument("-y", "--yes", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    return parser


def _split_passthrough(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" in argv:
        idx = argv.index("--")
        return argv[:idx], argv[idx + 1 :]
    return argv, []


def _parse_unknown_route_flags(unknown: list[str]) -> tuple[bool, list[str], dict]:
    extras: dict = {}
    launch = False
    extra: list[str] = []
    i = 0
    while i < len(unknown):
        tok = unknown[i]
        if tok == "--launch":
            launch = True
            i += 1
            continue
        if tok == "--with-fs":
            extras["with_fs"] = True
            i += 1
            continue
        if tok == "--no-plugin":
            extras["no_plugin"] = True
            i += 1
            continue
        if tok == "--local":
            extras["local"] = True
            i += 1
            continue
        if tok == "--scope" and i + 1 < len(unknown):
            extras["scope"] = unknown[i + 1]
            i += 2
            continue
        if tok.startswith("--scope="):
            extras["scope"] = tok.split("=", 1)[1]
            i += 1
            continue
        if tok == "--model" and i + 1 < len(unknown):
            extras["model"] = unknown[i + 1]
            i += 2
            continue
        if tok.startswith("--model="):
            extras["model"] = tok.split("=", 1)[1]
            i += 1
            continue
        if tok == "--profile" and i + 1 < len(unknown):
            extras["profile"] = unknown[i + 1]
            i += 2
            continue
        if tok.startswith("--profile="):
            extras["profile"] = tok.split("=", 1)[1]
            i += 1
            continue
        if tok == "--claude":
            extras["claude"] = True
            i += 1
            continue
        if tok == "--line":
            extras["line"] = True
            i += 1
            continue
        if tok == "--hook":
            extras["hook"] = True
            i += 1
            continue
        if tok == "--session-start":
            extras["session_start"] = True
            i += 1
            continue
        if tok == "--welcome-json":
            extras["welcome_json"] = True
            i += 1
            continue
        if tok == "--signup":
            extras["signup"] = True
            i += 1
            continue
        if tok in ("-y", "--yes"):
            extras["yes"] = True
            i += 1
            continue
        if tok == "--use":
            extras["use"] = True
            i += 1
            continue
        if tok == "--current":
            extras["current"] = True
            i += 1
            continue
        if tok == "--quiet":
            extras["quiet"] = True
            i += 1
            continue
        if tok == "--open":
            extras["open"] = True
            i += 1
            continue
        if tok == "--type" and i + 1 < len(unknown):
            extras["asset_type"] = unknown[i + 1]
            i += 2
            continue
        if tok.startswith("--type="):
            extras["asset_type"] = tok.split("=", 1)[1]
            i += 1
            continue
        if tok == "--email" and i + 1 < len(unknown):
            extras["email"] = unknown[i + 1]
            i += 2
            continue
        if tok == "--password" and i + 1 < len(unknown):
            extras["password"] = unknown[i + 1]
            i += 2
            continue
        if tok == "--name" and i + 1 < len(unknown):
            extras["name"] = unknown[i + 1]
            i += 2
            continue
        if tok == "--org" and i + 1 < len(unknown):
            extras["org"] = unknown[i + 1]
            i += 2
            continue
        if tok == "--workspace" and i + 1 < len(unknown):
            extras["workspace"] = unknown[i + 1]
            i += 2
            continue
        if tok == "--key" and i + 1 < len(unknown):
            extras["key"] = unknown[i + 1]
            i += 2
            continue
        if tok == "--description" and i + 1 < len(unknown):
            extras["description"] = unknown[i + 1]
            i += 2
            continue
        extra.append(tok)
        i += 1
    return launch, extra, extras


def _parse_route_tail(*, launch_flag: bool, remainder: list[str]) -> tuple[bool, list[str], dict]:
    launch, extra, extras = _parse_unknown_route_flags(remainder)
    return launch_flag or launch, extra, extras


def _print_profiles() -> int:
    from tokensaver_cli.credentials import resolve_plan_slug
    from tokensaver_cli.profiles import is_free_plan

    plan = resolve_plan_slug()
    print("TokenSaver model profiles")
    if is_free_plan(plan):
        print(f"  (plan: {plan} — Free allowlist defaults)")
    elif plan:
        print(f"  (plan: {plan})")
    else:
        print("  (plan unknown — paid/BYOK defaults; login to detect Free)")
    print()
    for row in profiles_summary(plan_slug=plan):
        tag = "builtin" if row["builtin"] else "custom"
        print(f"  {row['name']:12}  {row['model']}  ({tag})")
    print()
    print("Override: edit ~/.config/tokensaver/route/profiles.json")
    print("Usage:    tokensaver route claude --profile cheap")
    return 0


def main(argv: list[str] | None = None) -> None:
    raw = list(sys.argv[1:] if argv is None else argv)
    main_argv, passthrough = _split_passthrough(raw)

    parser = build_parser()
    args, unknown = parser.parse_known_args(main_argv)
    launch_unknown, extra_unknown, extras = _parse_unknown_route_flags(unknown)

    if args.help or args.command in (None, "help"):
        print_banner()
        print_usage()
        raise SystemExit(0)

    force_local = bool(args.local or extras.get("local"))

    if args.command == "profiles":
        print_banner()
        raise SystemExit(_print_profiles())

    if args.command == "models":
        print_banner()
        raise SystemExit(run_models(force_local=force_local))

    if args.command == "use":
        print_banner()
        choice = args.target or args.arg or (extra_unknown[0] if extra_unknown else None)
        raise SystemExit(
            run_use(
                choice,
                force_local=force_local,
                scope=extras.get("scope") or args.scope,
                with_fs=bool(args.with_fs or extras.get("with_fs")),
                launch=bool(args.launch or launch_unknown),
            )
        )

    if args.command == "flows":
        print_banner()
        raise SystemExit(
            run_flows(
                force_local=force_local,
                open_browser=bool(args.open or extras.get("open")),
            )
        )

    if args.command == "catalog":
        print_banner()
        action = (args.target or "list").strip().lower()
        if action not in CATALOG_ACTIONS:
            print("catalog action must be: list | pending | approve <ref>", file=sys.stderr)
            raise SystemExit(2)
        ref = args.arg or (extra_unknown[0] if extra_unknown else None)
        raise SystemExit(run_catalog(action, ref, force_local=force_local))

    if args.command == "login":
        print_banner()
        signup_flag: bool | None = True if (args.signup or extras.get("signup")) else None
        raise SystemExit(
            run_login(
                email=extras.get("email") or args.email,
                password=extras.get("password") or args.password,
                name=extras.get("name") or args.name,
                organisation=extras.get("org") or args.org,
                workspace=extras.get("workspace") or args.workspace,
                signup=signup_flag,
                api_key=extras.get("key") or args.key,
                force_local=force_local,
                yes=bool(args.yes or extras.get("yes")),
            )
        )

    if args.command == "logout":
        print_banner()
        raise SystemExit(run_logout())

    if args.command == "whoami":
        print_banner()
        raise SystemExit(run_whoami(force_local=force_local))

    if args.command == "verify-email":
        print_banner()
        tok = args.target or args.arg or (extra_unknown[0] if extra_unknown else None)
        if not tok:
            print("Usage: tokensaver verify-email <token-or-full-url>", file=sys.stderr)
            raise SystemExit(2)
        raise SystemExit(run_verify_email(tok, force_local=force_local))

    if args.command == "resend-verification":
        print_banner()
        raise SystemExit(run_resend_verification(force_local=force_local))

    if args.command == "keys":
        print_banner()
        action = (args.target or "list").strip().lower()
        if action not in KEYS_ACTIONS:
            print("keys action must be: list | create | revoke", file=sys.stderr)
            raise SystemExit(2)
        if action == "list":
            raise SystemExit(run_keys_list(force_local=force_local))
        if action == "create":
            raise SystemExit(
                run_keys_create(
                    name=(extras.get("name") or args.name or "CLI"),
                    description=extras.get("description") or args.description,
                    use=bool(args.use or extras.get("use")),
                    force_local=force_local,
                )
            )
        key_id = args.arg or (extra_unknown[0] if extra_unknown else None)
        if not key_id:
            print("Usage: tokensaver keys revoke <key-id>", file=sys.stderr)
            raise SystemExit(2)
        raise SystemExit(run_keys_revoke(key_id, force_local=force_local))

    if args.command == "approve":
        quiet = bool(args.quiet or extras.get("quiet"))
        if not quiet:
            print_banner()
        # `tokensaver approve openrouter/…` → target; `--current` uses settings model
        ref = args.target or args.arg or (extra_unknown[0] if extra_unknown else None)
        raise SystemExit(
            run_approve(
                ref,
                current=bool(args.current or extras.get("current") or not ref),
                asset_type=str(extras.get("asset_type") or args.asset_type or "model"),
                force_local=force_local,
                quiet=quiet,
            )
        )

    if args.command == "status":
        line = bool(args.line or extras.get("line"))
        hook = bool(args.hook or extras.get("hook"))
        session_start = bool(
            getattr(args, "session_start", False)
            or extras.get("session_start")
            or getattr(args, "welcome_json", False)
            or extras.get("welcome_json")
        )
        if not (line or hook or session_start):
            print_banner()
        raise SystemExit(
            run_status(line=line, hook=hook, session_start=session_start, welcome_json=session_start)
        )

    if args.command == "doctor":
        print_banner()
        claude = bool(args.claude or extras.get("claude"))
        raise SystemExit(run_doctor(claude=claude, force_local=force_local))

    if args.command == "unroute":
        print_banner()
        if not args.target or args.target not in UNROUTE_TARGETS:
            print("unroute requires a target:", ", ".join(UNROUTE_TARGETS), file=sys.stderr)
            raise SystemExit(2)
        handlers = {
            "claude": unroute_claude,
            "cursor": unroute_cursor,
            "codex": unroute_codex,
            "proxy": unroute_proxy,
            "mcp": unroute_mcp,
        }
        raise SystemExit(handlers[args.target]())

    if args.command != "route":
        print_banner()
        print_usage()
        raise SystemExit(2)

    if not args.target or args.target not in ROUTE_TARGETS:
        print("route requires a target:", ", ".join(ROUTE_TARGETS), file=sys.stderr)
        raise SystemExit(2)

    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print_banner()
    launch = bool(args.launch or launch_unknown or passthrough or extra_unknown)
    extra_args = [*extra_unknown, *passthrough]

    if args.target == "claude":
        scope = extras.get("scope") or args.scope or "user"
        model = extras.get("model") if "model" in extras else args.model
        profile = extras.get("profile") if "profile" in extras else args.profile
        with_fs = bool(args.with_fs or extras.get("with_fs"))
        install_plugin = not (args.no_plugin or extras.get("no_plugin"))
        raise SystemExit(
            route_claude(
                cfg,
                launch=launch,
                extra_args=extra_args,
                scope=scope,
                model=model,
                profile=profile,
                with_fs=with_fs,
                install_plugin=install_plugin,
            )
        )

    handlers = {
        "cursor": lambda: route_cursor(cfg),
        "codex": lambda: route_codex(cfg, launch=launch, extra_args=extra_args),
        "proxy": lambda: route_proxy(cfg),
        "mcp": lambda: route_mcp(cfg, target=args.mcp_target),
    }
    raise SystemExit(handlers[args.target]())


if __name__ == "__main__":
    main()
