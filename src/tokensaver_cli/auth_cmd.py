"""Auth commands: login, logout, whoami."""

from __future__ import annotations

import getpass
import sys
from typing import Any

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.config import (
    LOCAL_API_HOST,
    LOCAL_CONSOLE_URL,
    PROD_API_HOST,
    PROD_CONSOLE_URL,
    resolve_deploy_mode,
)
from tokensaver_cli.credentials import (
    Credentials,
    clear_credentials,
    credentials_path,
    load_credentials,
    resolve_access_token,
    resolve_api_key,
    save_credentials,
)


def _api_host(*, force_local: bool = False) -> str:
    import os

    mode = resolve_deploy_mode(force_local=force_local)
    default = LOCAL_API_HOST if mode == "local" else PROD_API_HOST
    host = (os.environ.get("TOKENSAVER_API_URL") or os.environ.get("TOKENSAVER_API_BASE_URL") or default).rstrip(
        "/"
    )
    if host.endswith("/api/v1"):
        host = host[: -len("/api/v1")]
    return host


def _console_url(*, force_local: bool = False, api_host: str | None = None) -> str:
    import os

    mode = resolve_deploy_mode(api_host=api_host, force_local=force_local)
    default = LOCAL_CONSOLE_URL if mode == "local" else PROD_CONSOLE_URL
    return (os.environ.get("TOKENSAVER_CONSOLE_URL") or default).rstrip("/")


def _api_v1(api_host: str) -> str:
    host = api_host.rstrip("/")
    if host.endswith("/api/v1"):
        return host
    return f"{host}/api/v1"


def _prompt(label: str, *, default: str | None = None, secret: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    if secret:
        value = getpass.getpass(f"{label}{hint}: ")
    else:
        value = input(f"{label}{hint}: ").strip()
    if not value and default is not None:
        return default
    return value.strip()


def _check_email(api_v1: str, email: str) -> bool | None:
    """Return True if email is available for signup, False if taken, None if check failed."""
    try:
        data = request_json("POST", f"{api_v1}/auths/check-email", body={"email": email})
        return bool(data.get("available"))
    except ApiError as exc:
        if exc.status == 403:
            print("Public signup is disabled on this deployment — use login with an existing account.", file=sys.stderr)
            return False
        print(f"WARN  email check failed: {exc}", file=sys.stderr)
        return None


def _ensure_cli_api_key(api_v1: str, access_token: str, *, label: str = "CLI") -> tuple[str, str | None, str | None]:
    """Create a CLI-labeled API key; returns (plain, id, prefix)."""
    data = request_json(
        "POST",
        f"{api_v1}/api-keys",
        headers={"Authorization": f"Bearer {access_token}"},
        body={"name": label},
    )
    plain = data.get("api_key") or data.get("key")
    if not plain:
        raise ApiError(500, "API key create returned no secret", url=f"{api_v1}/api-keys")
    return str(plain), data.get("id"), data.get("key_prefix")


def _fetch_me(api_v1: str, access_token: str) -> dict[str, Any]:
    return request_json(
        "GET",
        f"{api_v1}/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )


def run_login(
    *,
    email: str | None = None,
    password: str | None = None,
    name: str | None = None,
    organisation: str | None = None,
    workspace: str | None = None,
    signup: bool | None = None,
    api_key: str | None = None,
    force_local: bool = False,
    yes: bool = False,
) -> int:
    """Interactive or flag-driven login / signup. Persists credentials locally."""
    api_host = _api_host(force_local=force_local)
    console = _console_url(force_local=force_local, api_host=api_host)
    api_v1 = _api_v1(api_host)

    # Path A: import existing API key only (no JWT)
    if api_key and not email and not password and signup is not True:
        key = api_key.strip()
        if not key.startswith("ts_"):
            print("API key should start with ts_", file=sys.stderr)
            return 2
        creds = Credentials(
            api_key=key,
            key_prefix=key[:12],
            api_host=api_host,
            console_url=console,
        )
        path = save_credentials(creds)
        print(f"Saved API key to {path}")
        print("Next: tokensaver route claude --launch")
        print(f"Flux IA: {console}/fr/…/dashboard?tab=flows")
        return 0

    if not email:
        email = _prompt("Email")
    email = email.strip().lower()
    if not email or "@" not in email:
        print("A valid email is required.", file=sys.stderr)
        return 2

    available = _check_email(api_v1, email)
    do_signup = signup
    if do_signup is None:
        if available is True:
            do_signup = True
        elif available is False:
            do_signup = False
        else:
            # Ambiguous: ask
            choice = _prompt("Create a new account? [y/N]", default="n").lower()
            do_signup = choice in {"y", "yes"}

    if not password:
        password = _prompt("Password", secret=True)
    if len(password.encode("utf-8")) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 2

    action = "signup" if do_signup else "signin"
    try:
        if do_signup:
            if not name:
                name = _prompt("Your name", default=email.split("@")[0])
            if not organisation:
                organisation = _prompt("Organisation name", default=f"{name}'s org")
            if not workspace:
                workspace = _prompt("Workspace name", default="Default")
            if not yes:
                print(f"Creating Free account for {email} on {api_host} …")
            body = {
                "email": email,
                "password": password,
                "name": name or "",
                "organisation_name": organisation,
                "workspace_name": workspace,
                "create_key": True,
            }
            data = request_json("POST", f"{api_v1}/auths/signup", body=body)
        else:
            data = request_json(
                "POST",
                f"{api_v1}/auths/signin",
                body={"email": email, "password": password},
            )
    except ApiError as exc:
        print(f"FAIL  {action} — {exc}", file=sys.stderr)
        return 1

    access_token = data.get("token")
    if not access_token:
        print("FAIL  server did not return an access token", file=sys.stderr)
        return 1

    plain_key = data.get("api_key_plain") or api_key
    key_id = None
    key_prefix = None
    if plain_key:
        key_prefix = str(plain_key)[:12]
    else:
        try:
            plain_key, key_id, key_prefix = _ensure_cli_api_key(api_v1, str(access_token))
        except ApiError as exc:
            print(f"WARN  could not create API key: {exc}", file=sys.stderr)
            print("      You can run: tokensaver keys create --name CLI --use", file=sys.stderr)
            plain_key = None

    workspace_id = None
    organisation_id = None
    plan_slug = None
    try:
        me = _fetch_me(api_v1, str(access_token))
        ws = me.get("workspace") if isinstance(me.get("workspace"), dict) else {}
        org = me.get("organisation") if isinstance(me.get("organisation"), dict) else {}
        plan = me.get("plan") if isinstance(me.get("plan"), dict) else {}
        workspace_id = ws.get("id")
        organisation_id = org.get("id")
        plan_slug = plan.get("slug") or plan.get("name")
        if isinstance(plan_slug, str):
            plan_slug = plan_slug.strip().lower() or None
        if me.get("email"):
            email = str(me["email"])
    except ApiError as exc:
        print(f"WARN  /users/me failed: {exc}", file=sys.stderr)
        me = {}

    creds = Credentials(
        api_key=plain_key,
        access_token=str(access_token),
        email=email,
        user_id=str(data.get("id") or me.get("id") or "") or None,
        workspace_id=str(workspace_id) if workspace_id else None,
        organisation_id=str(organisation_id) if organisation_id else None,
        key_id=str(key_id) if key_id else None,
        key_prefix=key_prefix,
        api_host=api_host,
        console_url=console,
        plan_slug=str(plan_slug) if plan_slug else None,
    )
    path = save_credentials(creds)

    print()
    print(f"OK  Logged in as {email}")
    print(f"    Credentials → {path}")
    if plan_slug:
        print(f"    Plan        → {plan_slug}")
        if plan_slug == "free":
            print("    Default model for Free → openrouter/openai/gpt-oss-20b")
    if plain_key:
        print("    API key (shown once — copy now):")
        print(f"    {plain_key}")
    if data.get("email_verified") is False:
        print("    Verified:  NO — confirm your inbox before Claude / API (403 otherwise)")
        print("    CLI only:  tokensaver resend-verification")
        print("               tokensaver verify-email '<link from email>'")
    print()
    print("Next:")
    print("  tokensaver route claude --launch")
    print("  tokensaver status")
    ws = workspace_id or (creds.workspace_id if creds else None)
    if ws:
        print(f"  Flux IA → {console}/fr/{ws}/dashboard?tab=flows")
    else:
        print(f"  Flux IA → {console}/fr/<workspace>/dashboard?tab=flows")
    return 0


def _extract_verification_token(value: str) -> str:
    """Token from raw string or full verify-email URL (?token=…)."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if "token=" in raw:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(raw)
        qs = parse_qs(parsed.query)
        parts = qs.get("token") or []
        if parts and parts[0].strip():
            return parts[0].strip()
    return raw


def run_verify_email(token_or_url: str, *, force_local: bool = False) -> int:
    """Confirm email via link token (no console login required)."""
    token = _extract_verification_token(token_or_url)
    if not token:
        print("Usage: tokensaver verify-email <token>\n       tokensaver verify-email 'https://…/verify-email?token=…'", file=sys.stderr)
        return 2
    api_v1 = _api_v1(_api_host(force_local=force_local))
    try:
        data = request_json("POST", f"{api_v1}/auths/verify-email", body={"token": token})
    except ApiError as exc:
        print(f"FAIL  verify-email — {exc}", file=sys.stderr)
        return 1
    email = data.get("email") or "?"
    print(f"OK  Email verified for {email}")
    print("    You can use Claude Code / API immediately (no console login needed).")
    return 0


def run_resend_verification(*, force_local: bool = False) -> int:
    """Resend verification email (requires JWT from tokensaver login)."""
    token = resolve_access_token()
    if not token:
        print("Session JWT required. Run: tokensaver login", file=sys.stderr)
        return 1
    api_v1 = _api_v1(_api_host(force_local=force_local))
    try:
        data = request_json(
            "POST",
            f"{api_v1}/auths/resend-verification",
            headers={"Authorization": f"Bearer {token}"},
        )
    except ApiError as exc:
        print(f"FAIL  resend-verification — {exc}", file=sys.stderr)
        return 1
    print(data.get("message") or "Verification email sent.")
    print("Open the link in your inbox (works without logging into the console).")
    print("Or paste the URL: tokensaver verify-email '<link>'")
    return 0


def run_logout() -> int:
    if clear_credentials():
        print(f"Logged out — removed {credentials_path()}")
    else:
        print("No credentials file to remove.")
    print("Note: TOKENSAVER_API_KEY in your shell (if set) is unchanged.")
    return 0


def run_whoami(*, force_local: bool = False) -> int:
    creds = load_credentials()
    api_key = resolve_api_key()
    token = resolve_access_token()

    if not creds and not api_key and not token:
        print("Not logged in. Run: tokensaver login", file=sys.stderr)
        return 1

    api_host = (creds.api_host if creds and creds.api_host else None) or _api_host(force_local=force_local)
    console = (creds.console_url if creds and creds.console_url else None) or _console_url(
        force_local=force_local, api_host=api_host
    )
    api_v1 = _api_v1(api_host)

    print("TokenSaver identity")
    if creds and creds.email:
        print(f"  Email:     {creds.email}")
    if creds and creds.user_id:
        print(f"  User id:   {creds.user_id}")
    if api_key:
        import os

        src = "env" if (os.environ.get("TOKENSAVER_API_KEY") or "").strip() else "credentials"
        prefix = (creds.key_prefix if creds and creds.key_prefix else api_key[:12])
        print(f"  API key:   {prefix}… ({src})")
    print(f"  API host:  {api_host}")
    print(f"  Console:   {console}")

    if token:
        try:
            me = _fetch_me(api_v1, token)
            ws = me.get("workspace") if isinstance(me.get("workspace"), dict) else {}
            org = me.get("organisation") if isinstance(me.get("organisation"), dict) else {}
            plan = me.get("plan") if isinstance(me.get("plan"), dict) else {}
            if org.get("name"):
                print(f"  Org:       {org.get('name')} ({org.get('id', '')})")
            if ws.get("name"):
                print(f"  Workspace: {ws.get('name')} ({ws.get('id', '')})")
            verified = me.get("email_verified")
            required = me.get("email_verification_required")
            if required is not False:
                if verified is True:
                    print("  Verified:  yes")
                elif verified is False:
                    print("  Verified:  NO — API / Claude blocked until inbox confirmed")
                    print("             tokensaver resend-verification")
                    print("             tokensaver verify-email '<link from inbox>'")
            slug = plan.get("slug") or plan.get("name")
            if isinstance(slug, str) and slug.strip():
                slug_norm = slug.strip().lower()
                print(f"  Plan:      {plan.get('name') or slug_norm}")
                if creds is not None and creds.plan_slug != slug_norm:
                    from tokensaver_cli.credentials import update_credentials

                    update_credentials(plan_slug=slug_norm)
                if slug_norm == "free":
                    print("  Default:   openrouter/openai/gpt-oss-20b (Free allowlist)")
            trial = org.get("free_trial") if isinstance(org.get("free_trial"), dict) else None
            if trial:
                print(f"  Trial:     ends {trial.get('ends_at') or trial.get('free_trial_ends_at') or '—'}")
            ws_id = ws.get("id") or (creds.workspace_id if creds else None)
            if ws_id:
                print(f"  Flux IA:   {console}/fr/{ws_id}/dashboard?tab=flows")
            else:
                print(f"  Flux IA:   {console}/fr/<workspace>/dashboard?tab=flows")
        except ApiError as exc:
            print(f"  Session:   JWT present but /users/me failed ({exc})")
    else:
        print("  Session:   API key only (no JWT — run tokensaver login for keys management)")
        if creds and creds.plan_slug:
            print(f"  Plan:      {creds.plan_slug} (from credentials)")

    return 0
