"""Deterministic test validator (§9.6, §20.3). An LLM-generated test never runs unless this passes."""
import hashlib
import json
import re
from urllib.parse import urlsplit

from app.schemas import Action, ScanPolicy, TestCaseDef
from app.scope import DESTRUCTIVE_RE, ScopeError, check_url

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "navigate": ("url",),
    "click": ("target",),
    "fill": ("target", "value"),
    "select": ("target", "value"),
    "check": ("target",),
    "uncheck": ("target",),
    "press": ("key",),
    "hover": ("target",),
    "wait_for": ("target",),
    "screenshot": (),
    "assert_text": ("text",),
    "assert_visible": ("target",),
    "assert_hidden": ("target",),
    "assert_url": ("value",),
    "assert_title": ("value",),
    "assert_value": ("target", "value"),
    "assert_count": ("target", "count"),
    "assert_no_page_errors": (),
    "api_request": ("method", "url"),
    "assert_status": ("value",),
    "assert_json_schema": ("json_schema",),
    "assert_header": ("key",),
    "assert_header_not": ("key", "value"),
    "assert_body_not": ("value",),
    "assert_cookies_secure": (),
}
HTTP_TYPES = {"api_request", "assert_status", "assert_json_schema", "assert_header", "assert_header_not",
              "assert_body_not", "assert_cookies_secure"}
METHODS = {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}
CREDENTIAL_HEADERS = {"authorization", "cookie", "proxy-authorization", "x-api-key"}
MAX_STEPS = 40


def _target_text(a: Action) -> str:
    t = a.target
    return " ".join(filter(None, [t.name, t.label, t.text, t.test_id, t.css])) if t else ""


def validate(test: TestCaseDef, base_url: str, policy: ScanPolicy) -> list[str]:
    errors: list[str] = []
    if not test.steps:
        errors.append("test has no steps")
    if len(test.steps) > MAX_STEPS:
        errors.append(f"test has more than {MAX_STEPS} steps")
    if not any(s.type.startswith("assert_") for s in test.steps):
        errors.append("test has no assertions (every test needs an observable assertion)")
    http = bool(test.steps) and test.steps[0].type == "api_request"
    if test.steps and test.steps[0].type not in ("navigate", "api_request"):
        errors.append("first step must be navigate (browser test) or api_request (HTTP test)")
    if mixed := [s.type for s in test.steps if (s.type in HTTP_TYPES) != http]:
        errors.append(f"{'HTTP' if http else 'browser'} test contains steps of the other kind: {', '.join(mixed)}")
    if test.category == "security" and policy.security_profile == "off":
        errors.append("security tests are disabled by the scan policy (security_profile=off)")
    try:
        check_url(test.target_url, base_url, policy, resolve=False)
    except ScopeError as e:
        errors.append(f"target_url out of scope: {e}")

    for i, s in enumerate(test.steps, 1):
        missing = [f for f in REQUIRED_FIELDS[s.type] if getattr(s, f) in (None, "")]
        if missing:
            errors.append(f"step {i} ({s.type}) missing {', '.join(missing)}")
        if s.target and not any(s.target.model_dump().values()):
            errors.append(f"step {i} target has no locator")
        if s.type == "navigate" and s.url:
            try:
                check_url(s.url, base_url, policy, resolve=False)
            except ScopeError as e:
                errors.append(f"step {i} navigates out of scope: {e}")
        if s.type in ("click", "press") and DESTRUCTIVE_RE.search(_target_text(s)) and not policy.destructive_actions_allowed:
            errors.append(f"step {i} clicks a potentially destructive control ({_target_text(s)!r})")
        if s.type == "api_request":
            errors += [f"step {i}: {e}" for e in _check_request(s, test, base_url, policy)]
        for f in ("headers", "body", "json_schema"):
            if getattr(s, f):
                try:
                    json.loads(getattr(s, f))
                except ValueError:
                    errors.append(f"step {i} {f} is not valid JSON")
        if s.type in ("assert_header", "assert_header_not", "assert_body_not") and s.value:
            try:
                re.compile(s.value)
            except re.error as e:
                errors.append(f"step {i} pattern is not a valid regex: {e}")
    if test.side_effect == "destructive" and not policy.destructive_actions_allowed:
        errors.append("test is classified destructive and the scan policy forbids destructive actions")
    return errors


def _check_request(s: Action, test: TestCaseDef, base_url: str, policy: ScanPolicy) -> list[str]:
    """Safety rules for HTTP steps (§12.6, §29.4, §29.5)."""
    errors = []
    method = (s.method or "").upper()
    if method not in METHODS:
        errors.append(f"unsupported HTTP method {s.method!r}")
    if s.url:
        try:
            check_url(s.url, base_url, policy, resolve=False)
        except ScopeError as e:
            errors.append(f"request out of scope: {e}")
    path_words = urlsplit(s.url or "").path.replace("/", " ").replace("-", " ").replace("_", " ")
    if not policy.destructive_actions_allowed and (method == "DELETE" or DESTRUCTIVE_RE.search(path_words)):
        errors.append(f"{method} {urlsplit(s.url or '').path} looks destructive and the policy forbids it")
    if method not in ("GET", "HEAD", "OPTIONS"):
        if test.side_effect == "none":
            errors.append(f"{method} changes state: classify the test side_effect as writes_data")
        if test.category == "security" and policy.security_profile != "standard":
            errors.append("state-changing security probes need security_profile=standard")
    if s.headers:
        try:
            if creds := CREDENTIAL_HEADERS & {k.lower() for k in json.loads(s.headers)}:
                errors.append(f"credentials must not be stored in tests ({', '.join(sorted(creds))})")
        except (ValueError, AttributeError):
            pass  # reported as invalid JSON by the caller
    if s.value and s.value not in ("json", "form"):
        errors.append("api_request value must be the body encoding: json or form")
    return errors


def fingerprint(test: TestCaseDef) -> str:
    """Duplicate detection: identical step sequences are the same test regardless of wording."""
    steps = [s.model_dump(exclude={"description"}, exclude_none=True) for s in test.steps]
    return hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()
