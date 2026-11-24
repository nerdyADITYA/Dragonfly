"""Signing in to the application under test (§8.2 step 4, §21.1 step 4).

Login runs once per scan/run in its own browser context with tracing OFF, so the typed password never
lands in a Playwright trace or screenshot. Only the resulting session (cookies + storage) is handed to
the discovery/test contexts and the HTTP runner, in memory, and is never persisted.
"""
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.browser import isolated_page
from app.credentials import decrypt
from app.models import AuthProfile, Environment
from app.schemas import ScanPolicy
from app.scope import check_url

USERNAME_GUESS = ("input[type=email], input[autocomplete=username], input[name*=user i], input[name*=email i], "
                  "input[name*=login i], input[type=text]")


class LoginFailed(Exception):
    pass


def profile_for(db: Session, env: Environment) -> AuthProfile | None:
    return db.scalars(select(AuthProfile).where(AuthProfile.environment_id == env.id,
                                                AuthProfile.enabled.is_(True))).first()


def login(page, profile: AuthProfile, password: str, base_url: str, policy: ScanPolicy) -> str:
    """Fill and submit the login form; return the URL reached. Raises LoginFailed with a safe message."""
    check_url(profile.login_url, base_url, policy)
    page.goto(profile.login_url, wait_until="load")
    user = page.locator(profile.username_selector or USERNAME_GUESS).first
    pw = page.locator(profile.password_selector or "input[type=password]").first
    if not pw.count():
        raise LoginFailed(f"no password field found on {urlsplit(profile.login_url).path}")
    user.fill(profile.username)
    pw.fill(password)
    if profile.submit_selector:
        page.locator(profile.submit_selector).first.click()
    else:
        pw.press("Enter")
    page.wait_for_load_state("load")
    if profile.success_url_contains:
        ok = profile.success_url_contains in page.url
    else:  # default: we left the login page and no password field is showing
        ok = (urlsplit(page.url).path != urlsplit(profile.login_url).path
              and not page.locator("input[type=password]").first.is_visible())
    if not ok:
        raise LoginFailed(f"still on {urlsplit(page.url).path} after submitting credentials (wrong password, "
                          "captcha/MFA, or a different success URL)")
    return page.url


def session_state(db: Session, env: Environment) -> dict | None:
    """Sign in with the environment's profile and return Playwright storage state, or None if no profile."""
    profile = profile_for(db, env)
    if not profile:
        return None
    policy = ScanPolicy(**env.scan_policy)
    password = decrypt(profile.password_encrypted)
    with isolated_page(env.base_url, policy) as (page, ctx, _events):
        login(page, profile, password, env.base_url, policy)
        return ctx.storage_state()


def login_path(db: Session, env: Environment) -> str | None:
    p = profile_for(db, env)
    return urlsplit(p.login_url).path.rstrip("/") or "/" if p else None
