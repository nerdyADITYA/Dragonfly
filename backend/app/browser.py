"""Shared browser plumbing: isolated contexts with a scope-enforcing network guard and event collection."""
from contextlib import contextmanager
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from app.schemas import ScanPolicy
from app.scope import ScopeError, check_url


class Events:
    def __init__(self):
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.failed_requests: list[dict] = []
        self.blocked_requests: list[dict] = []
        self.api_calls: set[tuple[str, str]] = set()  # (method, url) of XHR/fetch requests

    def as_dict(self):
        return {"console_errors": self.console_errors[:50], "page_errors": self.page_errors[:50],
                "failed_requests": self.failed_requests[:50], "blocked_requests": self.blocked_requests[:50]}


def _redact_url(url: str) -> str:
    # Query strings may carry tokens; keep only scheme/host/path in evidence.
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}{p.path}" + ("?…" if p.query else "")


@contextmanager
def isolated_page(base_url: str, policy: ScanPolicy, record_trace: bool = False, storage_state: dict | None = None):
    """Yield (page, context, events). Every request is scope-checked; out-of-scope ones are aborted."""
    events = Events()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": policy.viewport_width, "height": policy.viewport_height},
                accept_downloads=False, service_workers="block", storage_state=storage_state,
            )
            if record_trace:
                context.tracing.start(screenshots=True, snapshots=True)

            def guard(route):
                url = route.request.url
                if url.startswith(("data:", "blob:", "about:")):
                    return route.continue_()
                try:
                    check_url(url, base_url, policy)
                except ScopeError as e:
                    events.blocked_requests.append({"url": _redact_url(url), "reason": str(e),
                                                    "type": route.request.resource_type})
                    return route.abort("blockedbyclient")
                route.continue_()

            context.route("**/*", guard)
            page = context.new_page()
            page.set_default_timeout(policy.step_timeout_ms)
            page.on("console", lambda m: m.type == "error" and events.console_errors.append(m.text[:500]))
            page.on("pageerror", lambda e: events.page_errors.append(str(e)[:500]))
            page.on("request", lambda r: r.resource_type in ("xhr", "fetch") and events.api_calls.add((r.method, r.url)))
            page.on("response", lambda r: r.status >= 400 and events.failed_requests.append(
                {"url": _redact_url(r.url), "status": r.status, "method": r.request.method}))
            page.on("requestfailed", lambda r: "ERR_BLOCKED_BY_CLIENT" not in (r.failure or "") and
                    events.failed_requests.append({"url": _redact_url(r.url), "status": None, "error": r.failure}))
            yield page, context, events
        finally:
            browser.close()


def screenshot(page) -> bytes:
    """Full-page screenshot with password fields masked (§13.4)."""
    return page.screenshot(full_page=True, mask=[page.locator("input[type=password]")])
