"""HTTP runner for API (§11) and security (§12) tests: no browser, scope-checked, rate-limited, budgeted.

Evidence is sanitized before storage (§13.4): credentials/cookies redacted, query strings dropped,
bodies truncated with secret-looking JSON values masked.
"""
import html
import json
import re
import time

import httpx
import jsonschema

from app.schemas import Action, ScanPolicy
from app.scope import ScopeError, check_url

USER_AGENT = "Dragonfly-QA/0.1 (authorized testing)"
# Signs that an error response exposes internals (§12.2 verbose errors / login error disclosure).
LEAK_PATTERN = (r"Traceback \(most recent call last\)|\bat [\w./\\-]+\.(?:py|js|ts|java|rb|php|go|cs):\d+"
                r"|\bWHERE\s+\w+\s*=|SQLSTATE|ORA-\d{5}|\bstack ?trace\b|Exception in thread")
# JSON keys that should never appear in API responses (§12.2 excessive data exposure).
SECRET_KEY_PATTERN = r'"(?:password|passwd|password_hash|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key)"\s*:'
_SECRET_VALUE = re.compile(r'("(?:password|passwd|password_hash|secret|api[_-]?key|access[_-]?token|refresh[_-]?token'
                           r'|private[_-]?key|token)"\s*:\s*)"[^"]*"', re.IGNORECASE)
REDACTED_HEADERS = {"authorization", "proxy-authorization", "cookie", "x-api-key"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
BODY_EXCERPT = 2000


class StepError(Exception):
    """The step could not be performed (not an assertion failure)."""


def _url(u: str) -> str:
    p = httpx.URL(u)
    return str(p.copy_with(query=None)) + ("?…" if p.query else "")


def _headers(h) -> dict:
    out = {}
    for k, v in h.multi_items():
        k = k.lower()
        if k in REDACTED_HEADERS:
            v = "•••"
        elif k == "set-cookie":  # keep cookie name + flags, never the value
            name, _, rest = v.partition("=")
            v = f"{name}=•••; " + "; ".join(x.strip() for x in rest.split(";")[1:])
        out[k] = f"{out[k]}\n{v}" if k in out else v
    return out


def evidence(resp: httpx.Response, elapsed_ms: int) -> dict:
    body = resp.text[:BODY_EXCERPT]
    return {"request": {"method": resp.request.method, "url": _url(str(resp.request.url)),
                        "headers": _headers(resp.request.headers)},
            "response": {"status": resp.status_code, "headers": _headers(resp.headers),
                         "body_excerpt": _SECRET_VALUE.sub(r'\1"•••"', body),
                         "truncated": len(resp.text) > BODY_EXCERPT},
            "elapsed_ms": elapsed_ms}


class HttpSession:
    def __init__(self, base_url: str, policy: ScanPolicy, budget: dict, cookies: list[dict] = ()):
        self.base, self.policy, self.budget = base_url, policy, budget
        jar = httpx.Cookies()
        for c in cookies:  # signed-in session from the login profile (Playwright storage-state format)
            jar.set(c["name"], c["value"], domain=c["domain"].lstrip("."), path=c.get("path", "/"))
        self.client = httpx.Client(timeout=policy.step_timeout_ms / 1000, follow_redirects=False,
                                   headers={"User-Agent": USER_AGENT}, cookies=jar)
        self.resp: httpx.Response | None = None
        self.current_evidence: dict | None = None  # evidence of the response being checked
        self.actual: str | None = None
        self.requests: list[dict] = []
        self._last_at = 0.0

    def close(self):
        self.client.close()

    def step(self, a: Action) -> dict | None:
        self.actual = None
        if a.type == "api_request":
            return self._request(a)
        if self.resp is None:
            raise StepError("no response to check: add an api_request step first")
        check = getattr(self, a.type, None) if a.type.startswith("assert_") else None
        if not check:
            raise StepError(f"{a.type} is not an HTTP step")
        return check(a)

    def actual_for(self, a: Action) -> str | None:
        return self.actual

    def _request(self, a: Action) -> None:
        check_url(a.url, self.base, self.policy)  # resolves DNS → SSRF guard on every request
        if self.budget["left"] <= 0:
            raise ScopeError(f"request budget exhausted (max_requests={self.policy.max_requests})")
        self.budget["left"] -= 1
        if (wait := 1 / self.policy.requests_per_second - (time.monotonic() - self._last_at)) > 0:
            time.sleep(wait)  # rate limit (§12.6)
        kw = {"headers": json.loads(a.headers) if a.headers else {}}
        if a.body:
            kw["data" if a.value == "form" else "json"] = json.loads(a.body)
        t0 = time.monotonic()
        self.resp = self.client.request(a.method.upper(), a.url, **kw)
        self._last_at = time.monotonic()
        self.current_evidence = evidence(self.resp, int((self._last_at - t0) * 1000))
        self.requests.append({"method": a.method.upper(), "url": _url(a.url), "status": self.resp.status_code})

    def _fail(self, actual: str, message: str):
        self.actual = actual
        raise AssertionError(message)

    # ---- assertions: return a record on pass, raise AssertionError on fail ----

    def assert_status(self, a: Action):
        code, want = str(self.resp.status_code), a.value.strip().lower()
        if not (code == want or (want.endswith("xx") and code[0] == want[0])):
            self._fail(code, f"expected HTTP {a.value}, got {code}")
        return {"type": a.type, "expected": a.value, "actual": code, "passed": True}

    def assert_json_schema(self, a: Action):
        try:
            data = self.resp.json()
        except ValueError:
            self._fail(self.resp.headers.get("content-type", ""), "response is not JSON")
        try:
            jsonschema.validate(data, json.loads(a.json_schema))
        except jsonschema.ValidationError as e:
            path = "/".join(str(p) for p in e.absolute_path) or "(root)"
            self._fail(f"{path}: {e.message[:300]}", f"response does not match schema at {path}")
        return {"type": a.type, "expected": "matches schema", "passed": True}

    def assert_header(self, a: Action):
        v = self.resp.headers.get(a.key)
        if v is None:
            self._fail("(missing)", f"response header {a.key} is missing")
        if a.value and not re.search(a.value, v, re.IGNORECASE):
            self._fail(v, f"header {a.key} = {v!r} does not match {a.value!r}")
        return {"type": a.type, "expected": f"{a.key} present", "actual": v, "passed": True}

    def assert_header_not(self, a: Action):
        v = self.resp.headers.get(a.key)
        if v is not None and re.search(a.value or ".", v, re.IGNORECASE):
            self._fail(v, f"header {a.key} = {v!r} matches forbidden pattern {a.value!r}")
        return {"type": a.type, "expected": f"{a.key} not matching {a.value!r}", "actual": v, "passed": True}

    def assert_body_not(self, a: Action):
        if m := re.search(a.value, self.resp.text, re.IGNORECASE):
            start = max(0, m.start() - 80)
            snippet = " ".join(html.unescape(re.sub(r"<[^>]*>|^[^<>]*>|<[^<>]*$", " ", self.resp.text[start:m.end() + 80])).split())
            self._fail(_SECRET_VALUE.sub(r'\1"•••"', snippet),
                       f"response contains forbidden content: {m.group(0)[:100]!r}")
        return {"type": a.type, "expected": "no forbidden content", "passed": True}

    def assert_cookies_secure(self, a: Action):
        https = self.resp.request.url.scheme == "https"
        bad = []
        for c in self.resp.headers.get_list("set-cookie"):
            flags = {x.strip().split("=")[0].lower() for x in c.split(";")[1:]}
            missing = [f for f in ("httponly", "samesite", *(["secure"] if https else [])) if f not in flags]
            if missing:
                bad.append(f"{c.split('=')[0]} (missing {', '.join(missing)})")
        if bad:
            self._fail("; ".join(bad), f"cookies without security flags: {'; '.join(bad)}")
        return {"type": a.type, "expected": "HttpOnly, SameSite (and Secure on HTTPS)", "passed": True}
