"""Bug intelligence (§14), tickets (§15) and fix verification (§16).

Facts come from the deterministic executor; AI only adds a clearly-labelled hypothesis.
Only a passing retest of the original test can mark a finding `verified`.
"""
import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import ai
from app.events import publish
from app.models import (
    FINDING_STATUSES,
    OPEN_FINDING_STATUSES,
    Developer,
    Environment,
    ExecutionStep,
    Finding,
    FindingEvent,
    TestCase,
    TestExecution,
    TestRun,
    Ticket,
)

log = logging.getLogger(__name__)
PROMPT_VERSION = "failure-analyst-v1"
SEVERITY_BY_PRIORITY = {"P0": "critical", "P1": "high", "P2": "medium", "P3": "low"}
SECRET_RE = re.compile(r"pass(word)?|secret|token|api[-_ ]?key|otp|pin\b|card|cvv|ssn", re.IGNORECASE)
# Statuses a human may set directly. `verified` only comes from a passing retest (§16.4).
MANUAL_STATUSES = set(FINDING_STATUSES) - {"verified", "duplicate"}


class FindingError(ValueError):
    pass


# ---------------- facts → readable evidence ----------------

def redact_action(a: dict) -> dict:
    """Mask typed values that look like secrets before they reach reports, tickets or AI prompts (§13.4, §29.5)."""
    t = a.get("target") or {}
    if a.get("type") == "fill" and SECRET_RE.search(" ".join(str(v) for v in t.values() if v)):
        return {**a, "value": "•••••• (redacted)"}
    if a.get("type") == "api_request" and a.get("body"):
        try:
            body = json.loads(a["body"])
        except ValueError:
            return {**a, "body": "(unparseable body redacted)"}
        if isinstance(body, dict):
            return {**a, "body": json.dumps({k: "•••" if SECRET_RE.search(k) else v for k, v in body.items()})}
    return a


def target_text(t: dict | None) -> str:
    t = {k: v for k, v in (t or {}).items() if v}
    if t.get("role") and t.get("name"):  # explicit: JSONB doesn't preserve key order
        return f'the "{t["name"]}" {t["role"]}'
    return ", ".join(f'{k} "{v}"' for k, v in t.items())


def describe(a: dict) -> str:
    t = target_text(a.get("target"))
    match a["type"]:
        case "navigate":
            return f"Open {a['url']}"
        case "click":
            return f"Click {t}"
        case "fill":
            return f'Type "{a.get("value")}" into {t}'
        case "select":
            return f'Choose "{a.get("value")}" in {t}'
        case "press":
            return f"Press {a.get('key')}" + (f" on {t}" if t else "")
        case "assert_url":
            return f'Expect the URL to contain "{a.get("value")}"'
        case "assert_title":
            return f'Expect the page title to contain "{a.get("value")}"'
        case "assert_text":
            return f'Expect the text "{a.get("text")}"' + (f" in {t}" if t else "")
        case "assert_visible" | "assert_hidden":
            return f"Expect {t} to be {a['type'].removeprefix('assert_')}"
        case "assert_value":
            return f'Expect {t} to have value "{a.get("value")}"'
        case "assert_count":
            return f"Expect {a.get('count')} element(s) matching {t}"
        case "assert_no_page_errors":
            return "Expect no uncaught JavaScript errors on the page"
        case "api_request":
            extra = " with headers " + a["headers"] if a.get("headers") else ""
            body = f" with a {a.get('value') or 'json'} body" if a.get("body") else ""
            return f"Send {a.get('method')} {a.get('url')}{extra}{body}"
        case "assert_status":
            return f"Expect HTTP status {a.get('value')}"
        case "assert_json_schema":
            return "Expect the response body to match the documented JSON schema"
        case "assert_header":
            return f'Expect response header "{a.get("key")}"' + (f' matching /{a["value"]}/' if a.get("value") else "")
        case "assert_header_not":
            return f'Expect response header "{a.get("key")}" not to match /{a.get("value")}/'
        case "assert_body_not":
            return "Expect the response not to reveal sensitive content (pattern check)"
        case "assert_cookies_secure":
            return "Expect cookies to be HttpOnly and SameSite (and Secure on HTTPS)"
    return f"{a['type'].replace('_', ' ').capitalize()} {t}".strip()


def _failed_step(db: Session, ex: TestExecution) -> ExecutionStep | None:
    return db.scalars(select(ExecutionStep).where(ExecutionStep.test_execution_id == ex.id,
                                                  ExecutionStep.status == "failed")).first()


def _facts(db: Session, ex: TestExecution) -> dict:
    defn = ex.definition_snapshot
    step = _failed_step(db, ex)
    n = step.step_number if step else len(defn["steps"])
    failed_assert = next((a for a in ex.assertion_results_json if not a.get("passed")), {})
    steps = [describe(redact_action(a)) for a in defn["steps"][:n]]
    expected = (defn["steps"][n - 1].get("description") or describe(defn["steps"][n - 1])) if step else ""
    if failed_assert.get("actual"):
        actual = f"Observed: {failed_assert['actual']}"
    else:
        actual = ((step.error_message if step else ex.failure_message) or "").split("\n")[0]
    return {"step": step, "step_number": n, "reproduction_steps": steps, "expected": expected,
            "actual": actual[:2000], "assertion": failed_assert}


def fingerprint(tc_id, step_number: int, action_type: str) -> str:
    """Same test failing at the same step = the same defect, across runs."""
    return hashlib.sha256(f"{tc_id}:{step_number}:{action_type}".encode()).hexdigest()


def event(db, f: Finding, event_type: str, message: str = "", actor: str = "system", **data):
    db.add(FindingEvent(finding_id=f.id, actor=actor, event_type=event_type, message=message, data_json=data))


# ---------------- AI failure analyst (§14.5, §20.5) ----------------

class FailureAnalysis(BaseModel):
    summary: str = Field(description="One or two sentences: what failed, in plain language")
    evidence: list[str] = Field(description="Concrete observations from the input that support the summary")
    likely_cause: str = Field(description="A HYPOTHESIS about the cause; never state it as proven")
    affected_component: str = Field(description="Page, form, endpoint or feature most likely involved")
    suggested_investigation: list[str]
    suggested_fix_direction: str
    confidence: Literal["low", "medium", "high"]


ANALYST_PROMPT = """You are the failure analyst inside Dragonfly. A deterministic Playwright test failed.
You get the test, the reproduction steps, the failed assertion and browser evidence. Explain the failure
for a developer. Base every statement on the evidence given; cite it in `evidence`. The cause is a hypothesis:
phrase it as one ("likely", "may"), and say so if the evidence is also consistent with a broken test
rather than an application defect. Keep it concise."""


def analyze(test: TestCase, facts: dict, ex: TestExecution) -> dict:
    events = ex.execution_metadata_json.get("browser_events", {})
    base = {"generated_at": datetime.now(UTC).isoformat(), "is_hypothesis": True}
    if ai.enabled():
        payload = {"test": {"title": test.title, "category": test.category,
                            "expected_outcomes": ex.definition_snapshot.get("expected_outcomes", [])},
                   "reproduction_steps": facts["reproduction_steps"], "failure_type": ex.failure_type,
                   "expected": facts["expected"], "actual": facts["actual"], "assertion": facts["assertion"],
                   "page_errors": events.get("page_errors", [])[:10], "console_errors": events.get("console_errors", [])[:10],
                   "failed_requests": events.get("failed_requests", [])[:10]}
        try:
            out = ai.structured(ANALYST_PROMPT, json.dumps(payload, ensure_ascii=False, default=str), FailureAnalysis,
                                max_tokens=4000)
            return {**base, **out.model_dump(), "provider": ai.model_tag(PROMPT_VERSION)}
        except Exception as e:  # analysis is optional; the finding stands on its evidence
            log.exception("failure analysis failed")
            return {**base, "provider": "rules", "error": f"AI analysis unavailable: {type(e).__name__}",
                    "summary": f"{test.title}: {facts['expected']} — {facts['actual']}"}
    return {**base, "provider": "rules", "summary": f"{test.title}: {facts['expected']} — {facts['actual']}",
            "evidence": [x for x in [facts["actual"], *events.get("page_errors", [])[:3]] if x],
            "likely_cause": "", "note": "Set ANTHROPIC_API_KEY for an AI-written hypothesis."}


# ---------------- detection ----------------

def record(db: Session, run: TestRun, ex: TestExecution) -> Finding | None:
    """Called for every finished execution. Creates/updates findings; resolves retests."""
    if run.retest_finding_id:
        f = db.get(Finding, run.retest_finding_id)
        if f and f.test_case_id == ex.test_case_id:
            return _resolve_retest(db, f, ex)
    # Only evidence of app behaviour becomes a finding; blocked/timeout/infrastructure do not (§57).
    if ex.status != "failed" or ex.failure_type not in ("assertion", "step_error"):
        return None
    tc = db.get(TestCase, ex.test_case_id)
    facts = _facts(db, ex)
    action = facts["step"].action_type if facts["step"] else "unknown"
    fp = fingerprint(tc.id, facts["step_number"], action)
    f = db.scalars(select(Finding).where(Finding.project_id == tc.project_id, Finding.fingerprint == fp)
                   .order_by(Finding.created_at.desc())).first()
    now = datetime.now(UTC)
    if f:
        f.occurrences += 1
        f.last_detected_at, f.last_execution_id, f.actual_result = now, ex.id, facts["actual"]
        if ex.failure_type == "assertion":
            f.confidence = "confirmed"  # reproduced in a separate execution
        msg = f"Failed again (occurrence {f.occurrences})"
        if f.status in ("fixed", "ready_for_retest", "verified"):
            f.status = "reopened"
            msg += "; reopened because it had been marked fixed/verified"
        event(db, f, "redetected", msg, execution_id=str(ex.id), run_id=str(run.id))
        db.commit()
        publish(f.project_id, "finding.updated", finding_id=f.id, status=f.status)
        return f

    defn = ex.definition_snapshot
    f = Finding(project_id=tc.project_id, environment_id=run.environment_id, test_case_id=tc.id,
                test_execution_id=ex.id, last_execution_id=ex.id, fingerprint=fp,
                title=f"{tc.title} — failed", category=tc.category, page_url=defn["target_url"],
                severity=SEVERITY_BY_PRIORITY.get(tc.priority, "medium"),
                confidence="probable" if ex.failure_type == "assertion" else "potential",
                description=defn.get("description") or "; ".join(defn.get("expected_outcomes", [])),
                expected_result=facts["expected"], actual_result=facts["actual"],
                reproduction_steps_json=facts["reproduction_steps"], first_detected_at=now, last_detected_at=now)
    db.add(f)
    db.flush()
    f.ai_analysis_json = analyze(tc, facts, ex)
    event(db, f, "detected", f"Detected by {tc.key} ({ex.failure_type})", execution_id=str(ex.id), run_id=str(run.id))
    db.commit()
    publish(f.project_id, "finding.created", finding_id=f.id, severity=f.severity)
    return f


def _resolve_retest(db: Session, f: Finding, ex: TestExecution) -> Finding:
    """§16.2 steps 8–10: pass → verified; same failure → reopened; anything else → human review."""
    ref = {"execution_id": str(ex.id), "run_id": str(ex.test_run_id), "result": ex.status}
    if ex.status == "passed":
        f.status = "verified"
        event(db, f, "retest", "Retest passed: original assertions now hold. Fix verified.", **ref)
    elif ex.status == "failed" and ex.failure_type in ("assertion", "step_error"):
        f.status, f.occurrences, f.last_execution_id = "reopened", f.occurrences + 1, ex.id
        f.last_detected_at = datetime.now(UTC)
        f.actual_result = _facts(db, ex)["actual"]
        if ex.failure_type == "assertion":
            f.confidence = "confirmed"
        event(db, f, "retest", "Retest failed: the defect is still present. Reopened.", **ref)
    else:
        event(db, f, "retest", f"Retest was {ex.status}; not treated as a fix. Needs human review.", **ref)
    db.commit()
    publish(f.project_id, "retest.completed", finding_id=f.id, result=ex.status, status=f.status)
    return f


# ---------------- lifecycle & triage ----------------

def set_status(db: Session, f: Finding, status: str, actor: str = "user", note: str = "") -> None:
    if status not in MANUAL_STATUSES:
        raise FindingError(f"'{status}' cannot be set manually" + (
            " — run a retest; only a passing retest verifies a fix" if status == "verified" else
            " — use mark-duplicate" if status == "duplicate" else ""))
    old, f.status = f.status, status
    event(db, f, "status", note or f"{old} → {status}", actor, old=old, new=status)


def set_severity(db: Session, f: Finding, severity: str, reason: str, actor: str = "user") -> None:
    if not reason.strip():
        raise FindingError("a reason is required to override severity (§12.5)")
    old, f.severity = f.severity, severity
    if t := ticket_for(db, f):
        t.severity = severity
    event(db, f, "severity", f"Severity {old} → {severity}: {reason}", actor, old=old, new=severity, reason=reason)


def mark_duplicate(db: Session, f: Finding, original: Finding, actor: str = "user") -> None:
    if original.id == f.id or original.project_id != f.project_id or original.duplicate_of_id == f.id:
        raise FindingError("invalid duplicate target")
    f.duplicate_of_id, old, f.status = original.id, f.status, "duplicate"
    event(db, f, "status", f"Marked duplicate of “{original.title}”", actor, old=old, new="duplicate",
          duplicate_of=str(original.id))


def duplicate_candidates(db: Session, f: Finding) -> list[Finding]:
    """Suggest, never auto-merge (§14.3): open findings on the same page with the same kind of failure."""
    path = urlsplit(f.page_url).path
    rows = db.scalars(select(Finding).where(Finding.project_id == f.project_id, Finding.id != f.id,
                                            Finding.status.in_(OPEN_FINDING_STATUSES))).all()
    return [o for o in rows if urlsplit(o.page_url).path == path and o.category == f.category][:5]


# ---------------- tickets (§15) ----------------

def ticket_for(db: Session, f: Finding) -> Ticket | None:
    return db.scalars(select(Ticket).where(Ticket.finding_id == f.id)).first()


def bug_report(db: Session, f: Finding, base_link: str = "") -> str:
    """Developer-ready markdown: facts first, AI hypothesis clearly labelled, no secrets."""
    env = db.get(Environment, f.environment_id)
    tc = db.get(TestCase, f.test_case_id)
    a = f.ai_analysis_json or {}
    lines = [
        f"**Severity:** {f.severity} · **Confidence:** {f.confidence} · **Category:** {f.category}",
        f"**Environment:** {env.name} ({env.base_url}) · **Detected by:** {tc.key} — {tc.title}",
        f"**First seen:** {f.first_detected_at:%Y-%m-%d %H:%M} UTC · **Occurrences:** {f.occurrences}", "",
        "### Steps to reproduce", *[f"{i}. {s}" for i, s in enumerate(f.reproduction_steps_json, 1)], "",
        "### Expected", f.expected_result or "—", "", "### Actual", f.actual_result or "—", "",
        "### Evidence",
        f"- Execution (screenshots, Playwright trace, console & network logs): {base_link}/executions/{f.test_execution_id}",
    ]
    if a.get("summary"):
        lines += ["", "### AI analysis (hypothesis — not a proven root cause)", a["summary"]]
        if a.get("likely_cause"):
            lines.append(f"- Likely cause: {a['likely_cause']}")
        if a.get("suggested_fix_direction"):
            lines.append(f"- Fix direction: {a['suggested_fix_direction']}")
    return "\n".join(lines)


def create_ticket(db: Session, f: Finding, assignee: Developer | None, base_link: str = "") -> Ticket:
    if ticket_for(db, f):
        raise FindingError("this finding already has a ticket")  # duplicate issue prevention (§15.6)
    if f.status in ("duplicate", "false_positive"):
        raise FindingError(f"finding is {f.status}; no ticket needed")
    number = (db.scalar(select(func.max(Ticket.number)).where(Ticket.project_id == f.project_id)) or 0) + 1
    t = Ticket(project_id=f.project_id, finding_id=f.id, number=number, title=f.title, severity=f.severity,
               description=bug_report(db, f, base_link))
    db.add(t)
    db.flush()
    event(db, f, "ticket", f"Ticket TP-{number} created", "user", ticket_id=str(t.id))
    if assignee:
        assign(db, f, t, assignee)
    return t


def assign(db: Session, f: Finding, t: Ticket, dev: Developer, actor: str = "user") -> None:
    if dev.project_id != f.project_id:
        raise FindingError("developer belongs to another project")
    t.assignee_id = dev.id
    if f.status in ("new", "triaged", "reopened"):
        f.status = "assigned"
    event(db, f, "assigned", f"Assigned to {dev.name}", actor, developer_id=str(dev.id))
