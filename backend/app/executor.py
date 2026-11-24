"""Test Execution Engine (§10, §21). Interprets the typed action schema with Playwright — no generated code runs.

Status model keeps assertion failures distinct from infrastructure problems:
  passed / failed (assertion | step_error) / blocked (scope) / timed_out / cancelled / inconclusive (infrastructure)
"""
import logging
import re
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx
from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import expect
from sqlalchemy.orm import Session

from app import findings, storage
from app.browser import isolated_page, screenshot
from app.events import publish
from app.http_checks import HttpSession, StepError
from app.models import Environment, ExecutionStep, Finding, TestCase, TestExecution, TestRun
from app.schemas import Action, ScanPolicy, TestCaseDef
from app.scope import ScopeError, check_url
from app.target_auth import session_state
from app.validator import validate

TERMINAL = {"passed", "failed", "blocked", "skipped", "timed_out", "cancelled", "inconclusive"}


class Cancelled(Exception):
    pass


class TestTimeout(Exception):
    __test__ = False


def locate(page, a: Action):
    t = a.target
    if t.role:
        return page.get_by_role(t.role, name=t.name, exact=False) if t.name else page.get_by_role(t.role)
    if t.label:
        return page.get_by_label(t.label)
    if t.placeholder:
        return page.get_by_placeholder(t.placeholder)
    if t.test_id:
        return page.get_by_test_id(t.test_id)
    if t.text:
        return page.get_by_text(t.text)
    return page.locator(t.css)


def run_step(page, a: Action, base_url: str, policy: ScanPolicy, timeout: int) -> dict | None:
    """Execute one action. Returns an assertion record for assert_* steps."""
    loc = locate(page, a).first if a.target else None
    match a.type:
        case "navigate":
            check_url(a.url, base_url, policy)
            page.goto(a.url, wait_until="load")
        case "click":
            loc.click(timeout=timeout)
            page.wait_for_load_state("load")
        case "fill":
            loc.fill(a.value, timeout=timeout)
        case "select":
            loc.select_option(a.value, timeout=timeout)
        case "check":
            loc.check(timeout=timeout)
        case "uncheck":
            loc.uncheck(timeout=timeout)
        case "press":
            (loc or page.keyboard).press(a.key, **({"timeout": timeout} if loc else {}))
            page.wait_for_load_state("load")
        case "hover":
            loc.hover(timeout=timeout)
        case "wait_for":
            loc.wait_for(state="visible", timeout=timeout)
        case "screenshot":
            pass  # handled by caller
        case "assert_text":
            target = loc or page.locator("body")
            expect(target).to_contain_text(a.text, timeout=timeout)
            return {"type": a.type, "expected": a.text, "passed": True}
        case "assert_visible":
            expect(loc).to_be_visible(timeout=timeout)
            return {"type": a.type, "expected": "visible", "passed": True}
        case "assert_hidden":
            expect(loc).to_be_hidden(timeout=timeout)  # also passes when the element doesn't exist
            return {"type": a.type, "expected": "hidden", "passed": True}
        case "assert_url":
            expect(page).to_have_url(re.compile(re.escape(a.value)), timeout=timeout)
            return {"type": a.type, "expected": f"URL contains {a.value!r}", "actual": page.url, "passed": True}
        case "assert_title":
            expect(page).to_have_title(re.compile(re.escape(a.value)), timeout=timeout)
            return {"type": a.type, "expected": f"title contains {a.value!r}", "actual": page.title(), "passed": True}
        case "assert_value":
            expect(loc).to_have_value(a.value, timeout=timeout)
            return {"type": a.type, "expected": a.value, "passed": True}
        case "assert_count":
            expect(locate(page, a)).to_have_count(a.count, timeout=timeout)
            return {"type": a.type, "expected": a.count, "passed": True}
    return None


def _actual(page, a: Action) -> str | None:
    """Best-effort observed value for a failed assertion (evidence for the bug report)."""
    try:
        if a.type == "assert_url":
            return page.url
        if a.type == "assert_title":
            return page.title()
        if a.type == "assert_count":
            return str(locate(page, a).count())
        if a.type == "assert_value":
            return locate(page, a).first.input_value(timeout=1000)
        if a.type == "assert_text":
            return (locate(page, a).first if a.target else page.locator("body")).inner_text(timeout=1000)[:500]
    except Exception:
        return None
    return None


class BrowserSession:
    """Playwright-backed steps (UI tests)."""

    def __init__(self, page, ctx, events, base_url: str, policy: ScanPolicy):
        self.page, self.ctx, self.events, self.base, self.policy = page, ctx, events, base_url, policy
        self.actual: str | None = None

    def step(self, a: Action) -> dict | None:
        self.actual = None
        if a.type == "assert_no_page_errors":
            if errs := self.events.page_errors:
                self.actual = errs[0]
                raise AssertionError(f"{len(errs)} uncaught JavaScript error(s), first: {errs[0]}")
            return {"type": a.type, "expected": "no uncaught JavaScript errors", "passed": True}
        return run_step(self.page, a, self.base, self.policy, self.policy.step_timeout_ms)

    def actual_for(self, a: Action) -> str | None:
        return self.actual or _actual(self.page, a)


@contextmanager
def _session(http: bool, env: Environment, policy: ScanPolicy, budget: dict, auth_state: dict | None):
    if http:
        s = HttpSession(env.base_url, policy, budget, cookies=(auth_state or {}).get("cookies", []))
        try:
            yield s
        finally:
            s.close()
    else:
        with isolated_page(env.base_url, policy, record_trace=True, storage_state=auth_state) as (page, ctx, events):
            yield BrowserSession(page, ctx, events, env.base_url, policy)


STEP_ERRORS = (PWTimeout, PWError, httpx.HTTPError, StepError)


def execute(db: Session, run: TestRun, tc: TestCase, env: Environment, attempt: int = 1,
            definition: dict | None = None, budget: dict | None = None, auth_state: dict | None = None,
            auth_error: str | None = None) -> TestExecution:
    """`definition` overrides the test's current version (retests replay the exact original snapshot).
    `budget` is the run-wide HTTP request budget shared by all tests in the run."""
    definition = definition or tc.definition_json
    policy = ScanPolicy(**env.scan_policy)
    budget = budget if budget is not None else {"left": policy.max_requests}
    test = TestCaseDef(**definition)
    ex = TestExecution(test_run_id=run.id, test_case_id=tc.id, test_case_version=tc.version,
                       definition_snapshot=definition, status="running", attempt_number=attempt,
                       started_at=datetime.now(UTC))
    db.add(ex)
    db.commit()
    publish(run.project_id, "test_execution.started", run_id=run.id, execution_id=ex.id, title=tc.title)

    # Re-validate at run time: policy may have changed since approval.
    if errors := validate(test, env.base_url, policy):
        ex.status, ex.failure_type, ex.failure_message = "blocked", "policy", "; ".join(errors)
        return _finish(db, ex)
    if auth_error:  # the app's login failed: results would be meaningless, so don't run (not an app defect)
        ex.status, ex.failure_type, ex.failure_message = "blocked", "auth", f"Sign-in to the target failed: {auth_error}"
        return _finish(db, ex)

    http = test.steps[0].type == "api_request"
    deadline = time.monotonic() + policy.test_timeout_seconds
    assertions: list[dict] = []
    t0 = time.monotonic()
    try:
        with _session(http, env, policy, budget, auth_state) as sess:
            failed = False
            for i, a in enumerate(test.steps, 1):
                db.refresh(run)
                if run.cancel_requested:
                    raise Cancelled()
                if time.monotonic() > deadline:
                    raise TestTimeout()
                st = ExecutionStep(test_execution_id=ex.id, step_number=i, action_type=a.type,
                                   action_definition_json=a.model_dump(exclude_none=True), status="passed")
                s0 = time.monotonic()
                try:
                    rec = sess.step(a)
                    if rec:
                        assertions.append({"step": i, **rec})
                    if not http and (a.type in ("navigate", "screenshot") or i == len(test.steps)):
                        st.screenshot_artifact_id = _shot(db, sess.page, run, ex)
                except AssertionError as e:
                    failed = True
                    st.status, st.error_message = "failed", str(e)[:2000]
                    ex.failure_type = "assertion"
                    ex.failure_message = f"Step {i} ({a.type}) failed: {a.description or e}".strip()
                    assertions.append({"step": i, "type": a.type, "passed": False, "actual": sess.actual_for(a),
                                       "expected": a.text or a.value or a.count or a.key, "message": str(e)[:1000]})
                except ScopeError as e:
                    failed = True
                    st.status, st.error_message = "failed", str(e)
                    ex.status, ex.failure_type, ex.failure_message = "blocked", "scope", str(e)
                except STEP_ERRORS as e:
                    failed = True
                    st.status, st.error_message = "failed", str(e)[:2000]
                    first_line = (str(e) or type(e).__name__).splitlines()[0][:300]
                    ex.failure_type = "step_error"
                    ex.failure_message = f"Step {i} ({a.type}) could not be performed: {first_line}"
                st.duration_ms = int((time.monotonic() - s0) * 1000)
                if http and (a.type == "api_request" or failed):
                    st.result_json = sess.current_evidence  # the response this step sent or checked
                if failed:
                    if not http:
                        st.screenshot_artifact_id = _shot(db, sess.page, run, ex)
                    db.add(st)
                    for j, rest in enumerate(test.steps[i:], i + 1):  # record remaining steps as skipped
                        db.add(ExecutionStep(test_execution_id=ex.id, step_number=j, action_type=rest.type,
                                             action_definition_json=rest.model_dump(exclude_none=True),
                                             status="skipped"))
                    break
                db.add(st)
                db.commit()
            ex.status = ex.status if ex.status == "blocked" else ("failed" if failed else "passed")
            meta = {"environment": env.name, "base_url": env.base_url}
            if http:
                ex.execution_metadata_json = {**meta, "runner": "http", "http_requests": sess.requests}
            else:
                if failed:
                    _save_trace(db, sess.ctx, run, ex)
                else:
                    sess.ctx.tracing.stop()
                ex.execution_metadata_json = {**meta, "runner": "browser", "browser": "chromium",
                                              "browser_events": sess.events.as_dict(),
                                              "viewport": [policy.viewport_width, policy.viewport_height]}
    except Cancelled:
        ex.status, ex.failure_type = "cancelled", None
    except TestTimeout:
        ex.status, ex.failure_type = "timed_out", "timeout"
        ex.failure_message = f"exceeded {policy.test_timeout_seconds}s"
    except Exception as e:  # browser launch/crash: not the app's fault, so inconclusive, never "failed"
        db.rollback()
        ex.status, ex.failure_type = "inconclusive", "infrastructure"
        ex.failure_message = f"{type(e).__name__}: {str(e)[:1000]}"
    ex.assertion_results_json = assertions
    ex.duration_ms = int((time.monotonic() - t0) * 1000)
    return _finish(db, ex)


def _shot(db, page, run, ex):
    try:
        return storage.save(db, screenshot(page), project_id=run.project_id, artifact_type="screenshot",
                            mime="image/png", ext="png", test_execution_id=ex.id).id
    except Exception:
        return None


def _save_trace(db, ctx, run, ex):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "trace.zip"
        try:
            ctx.tracing.stop(path=str(p))
        except Exception:
            return
        storage.save(db, p.read_bytes(), project_id=run.project_id, artifact_type="trace",
                     mime="application/zip", ext="zip", test_execution_id=ex.id)


def _finish(db, ex):
    ex.completed_at = datetime.now(UTC)
    db.commit()
    return ex


def run_tests(db: Session, run_id, test_case_ids: list) -> None:
    run = db.get(TestRun, run_id)
    env = db.get(Environment, run.environment_id)
    run.status, run.started_at = "running", datetime.now(UTC)
    db.commit()
    publish(run.project_id, "test_run.started", run_id=run.id)
    retest_tc = original_def = None
    state = auth_error = None
    try:
        state = session_state(db, env)  # sign in once per run; the session lives only in memory
    except Exception as e:
        auth_error = f"{type(e).__name__}: {str(e)[:300]}"
    budget = {"left": ScanPolicy(**env.scan_policy).max_requests}  # run-wide HTTP request cap (12.6)
    if run.retest_finding_id:  # retest replays the exact test version that detected the defect (§16.4)
        f = db.get(Finding, run.retest_finding_id)
        retest_tc, original_def = f.test_case_id, db.get(TestExecution, f.test_execution_id).definition_snapshot
    counts: dict[str, int] = {}
    for tc_id in test_case_ids:
        tc = db.get(TestCase, tc_id)
        db.refresh(run)
        if run.cancel_requested:
            status = "cancelled"
        elif not tc or (tc.status != "approved" and tc.id != retest_tc):
            status = "skipped"
        else:
            snap = original_def if tc.id == retest_tc else None
            ex = execute(db, run, tc, env, definition=snap, budget=budget, auth_state=state, auth_error=auth_error)
            # Retry only infrastructure failures, keeping the first attempt (§10.6).
            if ex.status == "inconclusive":
                ex = execute(db, run, tc, env, attempt=2, definition=snap, budget=budget, auth_state=state,
                             auth_error=auth_error)
            status = ex.status
            try:
                findings.record(db, run, ex)
            except Exception:  # the execution result is already saved; don't abort the remaining tests
                db.rollback()
                logging.getLogger(__name__).exception("recording finding failed for execution %s", ex.id)
        counts[status] = counts.get(status, 0) + 1
        publish(run.project_id, "test_execution.completed", run_id=run.id, test_case_id=tc_id, status=status)
    run.summary_json = {"counts": counts, "total": len(test_case_ids)}
    run.status = "cancelled" if run.cancel_requested else "completed"
    run.completed_at = datetime.now(UTC)
    db.commit()
    publish(run.project_id, "test_run.completed", run_id=run.id, finding_id=run.retest_finding_id)
