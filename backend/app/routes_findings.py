"""Findings, developers, tickets and retests (§27.7–27.8). Same no-auth shortcut as routes.py."""
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import findings as fx
from app.db import get_db
from app.models import Artifact, Developer, Environment, ExecutionStep, Finding, FindingEvent, TestCase, TestRun, Ticket
from app.routes import _start_run, get_or_404
from app.schemas import (
    AssignIn,
    CommentIn,
    DeveloperIn,
    DeveloperOut,
    DuplicateIn,
    FindingDetailOut,
    FindingOut,
    FindingPatch,
    RetestIn,
    TestRunOut,
    TicketIn,
    TicketOut,
)

router = APIRouter(prefix="/api/v1")


def _apply(db: Session, fn, *args, **kw):
    try:
        out = fn(db, *args, **kw)
    except fx.FindingError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return out


def _ui_base(request: Request) -> str:
    # Links in tickets point at the web UI the request came from (Vite proxies the API on the same origin).
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    return f"{urlsplit(origin).scheme}://{urlsplit(origin).netloc}" if origin else ""


def _ticket_out(db: Session, t: Ticket) -> TicketOut:
    out = TicketOut.model_validate(t)
    out.status = db.get(Finding, t.finding_id).status
    out.assignee = DeveloperOut.model_validate(db.get(Developer, t.assignee_id)) if t.assignee_id else None
    return out


def _failed_shot(db: Session, execution_id) -> uuid.UUID | None:
    step = db.scalars(select(ExecutionStep).where(ExecutionStep.test_execution_id == execution_id,
                                                  ExecutionStep.status == "failed")).first()
    if step and step.screenshot_artifact_id:
        return step.screenshot_artifact_id
    art = db.scalars(select(Artifact).where(Artifact.test_execution_id == execution_id,
                                            Artifact.artifact_type == "screenshot")
                     .order_by(Artifact.created_at.desc())).first()
    return art.id if art else None


# ---------------- findings ----------------

@router.get("/projects/{project_id}/findings", response_model=list[FindingOut])
def list_findings(project_id: uuid.UUID, status: str | None = None, severity: str | None = None,
                  open_only: bool = False, db: Session = Depends(get_db)):
    q = select(Finding).where(Finding.project_id == project_id)
    if status:
        q = q.where(Finding.status == status)
    if severity:
        q = q.where(Finding.severity == severity)
    if open_only:
        q = q.where(Finding.status.in_(fx.OPEN_FINDING_STATUSES))
    return db.scalars(q.order_by(Finding.last_detected_at.desc())).all()


@router.get("/findings/{finding_id}", response_model=FindingDetailOut)
def get_finding(finding_id: uuid.UUID, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    t = fx.ticket_for(db, f)
    return FindingDetailOut(
        **FindingOut.model_validate(f).model_dump(),
        events=db.scalars(select(FindingEvent).where(FindingEvent.finding_id == f.id)
                          .order_by(FindingEvent.created_at)).all(),
        ticket=_ticket_out(db, t) if t else None,
        retest_runs=db.scalars(select(TestRun).where(TestRun.retest_finding_id == f.id)
                               .order_by(TestRun.created_at.desc())).all(),
        duplicate_candidates=fx.duplicate_candidates(db, f),
        original_screenshot_id=_failed_shot(db, f.test_execution_id),
        latest_screenshot_id=_failed_shot(db, f.last_execution_id),
    )


@router.patch("/findings/{finding_id}", response_model=FindingOut)
def patch_finding(finding_id: uuid.UUID, body: FindingPatch, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    try:
        if body.severity and body.severity != f.severity:
            fx.set_severity(db, f, body.severity, body.reason)
        if body.status and body.status != f.status:
            fx.set_status(db, f, body.status, note=body.reason)
    except fx.FindingError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return f


@router.post("/findings/{finding_id}/duplicate", response_model=FindingOut)
def mark_duplicate(finding_id: uuid.UUID, body: DuplicateIn, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    _apply(db, fx.mark_duplicate, f, get_or_404(db, Finding, body.duplicate_of_id))
    return f


@router.post("/findings/{finding_id}/comments", status_code=201)
def comment(finding_id: uuid.UUID, body: CommentIn, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    fx.event(db, f, "comment", body.body, "user")
    db.commit()
    return {"ok": True}


@router.get("/findings/{finding_id}/report")
def report(finding_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    return {"title": f.title, "markdown": fx.bug_report(db, f, _ui_base(request))}


@router.post("/findings/{finding_id}/retest", response_model=TestRunOut, status_code=202)
def retest(finding_id: uuid.UUID, body: RetestIn, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    if f.status in ("duplicate", "false_positive", "wont_fix", "verified"):
        raise HTTPException(409, f"finding is {f.status}; nothing to retest")
    env = db.get(Environment, f.environment_id)
    if not env.authorization_confirmed or env.status != "active":
        raise HTTPException(409, "environment is not authorized/active")
    if db.scalars(select(TestRun).where(TestRun.retest_finding_id == f.id,
                                        TestRun.status.in_(("queued", "running")))).first():
        raise HTTPException(409, "a retest is already running")
    ids = [f.test_case_id]
    if body.include_related:  # MVP regression selection: approved tests on the same page (§16.3)
        path = urlsplit(f.page_url).path
        ids += [t.id for t in db.scalars(select(TestCase).where(TestCase.project_id == f.project_id,
                                                                TestCase.status == "approved",
                                                                TestCase.id != f.test_case_id)).all()
                if urlsplit(t.definition_json["target_url"]).path == path]
    old, f.status = f.status, "ready_for_retest"
    fx.event(db, f, "status", f"{old} → ready_for_retest (retest requested)", "user", old=old, new=f.status)
    db.commit()
    return _start_run(db, f.project_id, env.id, ids, retest_finding_id=f.id)


# ---------------- developers ----------------

@router.get("/projects/{project_id}/developers", response_model=list[DeveloperOut])
def list_devs(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(Developer).where(Developer.project_id == project_id).order_by(Developer.name)).all()


@router.post("/projects/{project_id}/developers", response_model=DeveloperOut, status_code=201)
def add_dev(project_id: uuid.UUID, body: DeveloperIn, db: Session = Depends(get_db)):
    from app.models import Project

    get_or_404(db, Project, project_id)
    d = Developer(project_id=project_id, **body.model_dump())
    db.add(d)
    db.commit()
    return d


@router.delete("/developers/{dev_id}", status_code=204)
def delete_dev(dev_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Developer, dev_id))
    db.commit()


# ---------------- tickets ----------------

@router.post("/findings/{finding_id}/ticket", response_model=TicketOut, status_code=201)
def create_ticket(finding_id: uuid.UUID, body: TicketIn, request: Request, db: Session = Depends(get_db)):
    f = get_or_404(db, Finding, finding_id)
    dev = get_or_404(db, Developer, body.assignee_id) if body.assignee_id else None
    t = _apply(db, fx.create_ticket, f, dev, _ui_base(request))
    return _ticket_out(db, t)


@router.get("/projects/{project_id}/tickets", response_model=list[TicketOut])
def list_tickets(project_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = db.scalars(select(Ticket).where(Ticket.project_id == project_id).order_by(Ticket.number.desc())).all()
    return [_ticket_out(db, t) for t in rows]


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)):
    return _ticket_out(db, get_or_404(db, Ticket, ticket_id))


@router.post("/tickets/{ticket_id}/assign", response_model=TicketOut)
def assign(ticket_id: uuid.UUID, body: AssignIn, db: Session = Depends(get_db)):
    t = get_or_404(db, Ticket, ticket_id)
    _apply(db, fx.assign, db.get(Finding, t.finding_id), t, get_or_404(db, Developer, body.developer_id))
    return _ticket_out(db, t)
