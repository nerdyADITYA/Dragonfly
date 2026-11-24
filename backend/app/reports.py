"""Dashboard metrics (§17.1) and the scan report (§17.2–17.3).

Every number is a plain count over stored rows, and the report states its limitations (§17.4, §51).
shortcut: aggregates in Python over the project's rows; move to SQL GROUP BYs when projects reach ~100k executions.
"""
import base64
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.db import get_db
from app.models import (
    OPEN_FINDING_STATUSES,
    Artifact,
    DiscoveredPage,
    Environment,
    ExecutionStep,
    Finding,
    Project,
    ScanRun,
    TestCase,
    TestExecution,
    TestRun,
)
from app.routes import get_or_404

router = APIRouter(prefix="/api/v1")
VERDICTS = ("passed", "failed")
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _where(model, project_id):
    q = select(model)
    return q.where(model.project_id == project_id) if project_id else q


@router.get("/dashboard")
def dashboard(project_id: uuid.UUID | None = None, days: int = 14, db: Session = Depends(get_db)):
    runs = {r.id: r for r in db.scalars(_where(TestRun, project_id)).all()}
    exs = db.scalars(select(TestExecution).where(TestExecution.test_run_id.in_(runs))).all() if runs else []
    findings = db.scalars(_where(Finding, project_id)).all()
    scans = db.scalars(_where(ScanRun, project_id).order_by(ScanRun.created_at.desc())).all()
    status = Counter(e.status for e in exs)
    decided = status["passed"] + status["failed"]
    durations = [e.duration_ms for e in exs if e.duration_ms is not None and e.status in VERDICTS]
    open_f = [f for f in findings if f.status in OPEN_FINDING_STATUSES]

    # Trend: executions per day by verdict.
    since = (datetime.now(UTC) - timedelta(days=days - 1)).date()
    trend = {since + timedelta(days=i): Counter() for i in range(days)}
    for e in exs:
        if e.started_at and (d := e.started_at.date()) in trend:
            trend[d][e.status if e.status in VERDICTS else "other"] += 1

    # Mixed recent results per test: flaky OR recently fixed/broken — labelled honestly in the UI.
    by_test = defaultdict(list)
    for e in sorted(exs, key=lambda e: e.started_at or datetime.min.replace(tzinfo=UTC), reverse=True):
        if e.status in VERDICTS and len(by_test[e.test_case_id]) < 10:
            by_test[e.test_case_id].append(e.status)
    mixed_ids = [tid for tid, s in by_test.items() if "passed" in s and "failed" in s]
    tcs = {t.id: t for t in db.scalars(select(TestCase).where(TestCase.id.in_(mixed_ids))).all()} if mixed_ids else {}

    return {
        "scope": {"project_id": project_id, "days": days},
        "projects": len(db.scalars(select(Project.id) if not project_id else
                                   select(Project.id).where(Project.id == project_id)).all()),
        "environments": len(db.scalars(_where(Environment, project_id)).all()),
        "scans": len(scans),
        "test_runs": len(runs),
        "executions": {"total": len(exs), **{k: status[k] for k in
                                            ("passed", "failed", "blocked", "inconclusive", "timed_out", "cancelled")}},
        "pass_rate": round(status["passed"] / decided, 4) if decided else None,
        "pass_rate_formula": "passed ÷ (passed + failed); blocked, inconclusive, timed out and cancelled are excluded",
        "avg_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "findings": {"total": len(findings), "open": len(open_f),
                     "open_by_severity": {s: sum(f.severity == s for f in open_f)
                                          for s in ("critical", "high", "medium", "low", "info")},
                     "reopened": sum(f.status == "reopened" for f in findings),
                     "verified": sum(f.status == "verified" for f in findings)},
        "trend": [{"date": d.isoformat(), "passed": c["passed"], "failed": c["failed"], "other": c["other"]}
                  for d, c in trend.items()],
        "mixed_results": [{"test_case_id": tid, "key": tcs[tid].key, "title": tcs[tid].title,
                           "passed": by_test[tid].count("passed"), "failed": by_test[tid].count("failed")}
                          for tid in mixed_ids if tid in tcs],
        "recent_scans": [{"id": s.id, "project_id": s.project_id, "status": s.status, "created_at": s.created_at,
                          "pages": (s.summary_json or {}).get("pages")} for s in scans[:5]],
        "recent_findings": [{"id": f.id, "title": f.title, "severity": f.severity, "status": f.status,
                             "last_detected_at": f.last_detected_at}
                            for f in sorted(findings, key=lambda f: f.last_detected_at, reverse=True)[:5]],
    }


# ---------------- scan report ----------------

CSS = """body{font:14px/1.5 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#0f172a}
h1{margin-bottom:0}h2{border-bottom:1px solid #e2e8f0;padding-bottom:.25rem;margin-top:2rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0}td,th{border:1px solid #e2e8f0;padding:.3rem .5rem;text-align:left;vertical-align:top}
th{background:#f8fafc}.muted{color:#64748b}.b{display:inline-block;padding:0 .4rem;border-radius:4px;font-size:12px;background:#f1f5f9}
.passed,.verified{background:#dcfce7}.failed,.critical,.high{background:#fee2e2}.medium,.blocked{background:#ffedd5}
.finding{border:1px solid #e2e8f0;border-radius:8px;padding:.75rem 1rem;margin:1rem 0}img{max-width:100%;border:1px solid #e2e8f0}
.hyp{border-left:3px solid #f59e0b;padding-left:.5rem}"""


def _b(text) -> str:
    return f'<span class="b {escape(str(text))}">{escape(str(text))}</span>'


def _img(db: Session, execution_id) -> str:
    step = db.scalars(select(ExecutionStep).where(ExecutionStep.test_execution_id == execution_id,
                                                  ExecutionStep.status == "failed")).first()
    art = db.get(Artifact, step.screenshot_artifact_id) if step and step.screenshot_artifact_id else None
    try:
        data = storage.path_for(art).read_bytes() if art else None
    except (OSError, ValueError):
        data = None
    return f'<img alt="Screenshot at failure" src="data:image/png;base64,{base64.b64encode(data).decode()}">' if data else ""


def build_scan_report(db: Session, scan: ScanRun) -> str:
    project, env = db.get(Project, scan.project_id), db.get(Environment, scan.environment_id)
    s, policy = scan.summary_json or {}, scan.scan_policy_snapshot
    pages = db.scalars(select(DiscoveredPage).where(DiscoveredPage.scan_run_id == scan.id)
                       .order_by(DiscoveredPage.depth, DiscoveredPage.created_at)).all()
    tests = db.scalars(select(TestCase).where(TestCase.scan_run_id == scan.id).order_by(TestCase.key)).all()
    tids = [t.id for t in tests]
    latest: dict = {}
    for e in db.scalars(select(TestExecution).where(TestExecution.test_case_id.in_(tids))
                        .order_by(TestExecution.started_at)).all() if tids else []:
        latest[e.test_case_id] = e  # ascending order → last write wins = most recent
    findings = db.scalars(select(Finding).where(Finding.test_case_id.in_(tids))).all() if tids else []
    findings.sort(key=lambda f: SEVERITY_RANK.get(f.severity, 9))
    verdicts = Counter(e.status for e in latest.values())
    duration = (scan.completed_at - scan.started_at).total_seconds() if scan.completed_at and scan.started_at else None
    open_f = [f for f in findings if f.status in OPEN_FINDING_STATUSES]

    h = [(f"<!doctype html><html lang=en><meta charset=utf-8><title>Dragonfly report · {escape(project.name)}</title>"
         f"<style>{CSS}</style><body>"),
         (f"<h1>Dragonfly scan report</h1><p class=muted>{escape(project.name)} · {escape(env.name)} "
         f"({escape(env.base_url)}) · generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC</p>"),
         "<h2>Summary</h2>",
         (f"<p>Discovery {_b(scan.status)} found <b>{len(pages)}</b> pages. <b>{len(tests)}</b> tests were generated "
         f"from it; <b>{len(latest)}</b> have been executed (latest result: {verdicts['passed']} passed, "
         f"{verdicts['failed']} failed, {len(latest) - verdicts['passed'] - verdicts['failed']} other). "
         f"<b>{len(open_f)}</b> open findings, {sum(f.status == 'verified' for f in findings)} verified fixed.</p>"),
         "<h2>Scan configuration</h2><table>",
         f"<tr><th>Started</th><td>{scan.started_at:%Y-%m-%d %H:%M:%S} UTC</td></tr>" if scan.started_at else "",
         f"<tr><th>Duration</th><td>{duration:.0f}s</td></tr>" if duration is not None else "",
         f"<tr><th>Allowed hosts</th><td>{escape(', '.join(policy.get('allowed_domains') or []) or 'base URL host')}</td></tr>",
         f"<tr><th>Excluded paths</th><td>{escape(', '.join(policy.get('excluded_paths') or []) or 'none')}</td></tr>",
         (f"<tr><th>Limits</th><td>{policy.get('max_pages')} pages, depth {policy.get('max_depth')}, "
         f"{policy.get('max_duration_seconds')}s</td></tr>"),
         f"<tr><th>Destructive actions</th><td>{'allowed' if policy.get('destructive_actions_allowed') else 'blocked'}</td></tr>",
         f"<tr><th>Stopped because</th><td>{escape(str(s.get('stopped_reason', '—')))}</td></tr></table>",
         f"<h2>Discovery ({len(pages)} pages, {s.get('elements', 0)} elements, {s.get('forms', 0)} forms)</h2>",
         (f"<p class=muted>Skipped {s.get('skipped_destructive', 0)} destructive-looking links and blocked "
         f"{s.get('skipped_out_of_scope', 0)} out-of-scope URLs.</p>"),
         "<table><tr><th>Depth</th><th>Page</th><th>URL</th><th>HTTP</th></tr>",
         *[f"<tr><td>{p.depth}</td><td>{escape(p.title)}</td><td>{escape(p.url)}</td><td>{p.status_code or ''}</td></tr>"
           for p in pages], "</table>",
         f"<h2>Test results ({len(tests)} tests)</h2>",
         "<table><tr><th>Key</th><th>Test</th><th>Category</th><th>Review</th><th>Latest result</th></tr>",
         *[f"<tr><td>{escape(t.key)}</td><td>{escape(t.title)}</td><td>{escape(t.category)}</td><td>{_b(t.status)}</td>"
           f"<td>{_b(latest[t.id].status) if t.id in latest else '<span class=muted>not run</span>'}</td></tr>"
           for t in tests], "</table>",
         "<h2>Security checks</h2><p class=muted>Not performed: security scanning is not part of this version.</p>",
         f"<h2>Findings ({len(findings)})</h2>"]
    if not findings:
        h.append("<p class=muted>No findings.</p>")
    for f in findings:
        a = f.ai_analysis_json or {}
        h += [(f'<div class=finding><h3>{escape(f.title)}</h3><p>{_b(f.severity)} {_b(f.confidence)} {_b(f.status)} '
              f'<span class=muted>seen {f.occurrences}× · {escape(f.page_url)}</span></p>'),
              "<p><b>Steps to reproduce</b></p><ol>",
              *[f"<li>{escape(x)}</li>" for x in f.reproduction_steps_json], "</ol>",
              f"<p><b>Expected:</b> {escape(f.expected_result)}<br><b>Actual:</b> {escape(f.actual_result)}</p>",
              _img(db, f.test_execution_id)]
        if a.get("summary"):
            h.append(f'<p class=hyp><b>AI analysis (hypothesis, not a proven root cause):</b> {escape(a["summary"])}'
                     + (f"<br>Likely cause: {escape(a['likely_cause'])}" if a.get("likely_cause") else "") + "</p>")
        h.append("</div>")
    limits = [*s.get("limitations", []), "Results describe this environment at scan time only.",
              "A passing test shows the asserted behaviour held, not that the page is defect-free."]
    h += ["<h2>Limitations</h2><ul>", *[f"<li>{escape(x)}</li>" for x in limits], "</ul></body></html>"]
    return "".join(h)


@router.get("/scan-runs/{scan_id}/report", response_class=HTMLResponse)
def scan_report(scan_id: uuid.UUID, download: bool = False, db: Session = Depends(get_db)):
    scan = get_or_404(db, ScanRun, scan_id)
    if scan.status in ("queued", "running"):
        raise HTTPException(409, "scan is still running")
    headers = {"Content-Disposition": f'attachment; filename="dragonfly-report-{scan_id}.html"'} if download else {}
    return HTMLResponse(build_scan_report(db, scan), headers=headers)

