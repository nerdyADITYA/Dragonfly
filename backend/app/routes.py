"""REST API v1 (§27): projects, environments, discovery, test cases, runs, artifacts.

Every route requires a signed-in user (router dependency `auth.authenticate`), which also tenant-checks
ids in the URL; `get_or_404` tenant-checks ids that arrive in request bodies.
"""
import uuid
from collections import Counter
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import storage
from app.auth import AuthCtx, actor, authenticate, can_access, require_admin
from app.browser import isolated_page
from app.credentials import CredentialError, decrypt, encrypt
from app.db import get_db
from app.models import (
    ApplicationEdge,
    Artifact,
    AuditLog,
    AuthProfile,
    DiscoveredPage,
    Environment,
    Project,
    ScanRun,
    TestCase,
    TestCaseVersion,
    TestExecution,
    TestRun,
)
from app.planner import generate_tests, regenerate_test, set_definition
from app.schemas import (
    ArtifactOut,
    AuthProfileIn,
    AuthProfileOut,
    DiscoveryIn,
    EnvironmentIn,
    EnvironmentOut,
    EnvironmentPatch,
    ExecutionDetailOut,
    GenerateTestsIn,
    PageOut,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    RegenerateIn,
    ScanPolicy,
    ScanRunOut,
    TestCaseDef,
    TestCaseOut,
    TestCasePatch,
    TestCaseVersionOut,
    TestRunDetailOut,
    TestRunIn,
    TestRunOut,
)
from app.scope import ScopeError, check_url
from app.target_auth import LoginFailed, login

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)])


def get_or_404(db: Session, model, id_: uuid.UUID):
    obj = db.get(model, id_)
    if not obj or not can_access(db, obj):  # tenant check for ids that arrive in bodies, not just URLs
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def audit(db, message, source="api", **kw):
    db.add(AuditLog(source=source, message=message, actor=actor(db), **kw))


# ---------------- projects ----------------

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(ctx: AuthCtx = Depends(authenticate), db: Session = Depends(get_db)):
    return db.scalars(select(Project).where(Project.organization_id == ctx.org_id)
                      .order_by(Project.created_at.desc())).all()


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, ctx: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    p = Project(**body.model_dump(), organization_id=ctx.org_id)
    db.add(p)
    db.flush()
    audit(db, f"project created: {p.name}", project_id=p.id)
    db.commit()
    return p


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, Project, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def patch_project(project_id: uuid.UUID, body: ProjectPatch, _: AuthCtx = Depends(require_admin),
                  db: Session = Depends(get_db)):
    p = get_or_404(db, Project, project_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    audit(db, "project updated", project_id=p.id, metadata_json=body.model_dump(exclude_unset=True))
    db.commit()
    return p


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, _: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Project, project_id))
    db.commit()


# ---------------- environments ----------------

def _validate_env(base_url: str, policy: ScanPolicy):
    try:
        check_url(base_url, base_url, policy)
    except ScopeError as e:
        raise HTTPException(422, f"base_url rejected by scope policy: {e}")


@router.get("/projects/{project_id}/environments", response_model=list[EnvironmentOut])
def list_envs(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(Environment).where(Environment.project_id == project_id)).all()


@router.post("/projects/{project_id}/environments", response_model=EnvironmentOut, status_code=201)
def create_env(project_id: uuid.UUID, body: EnvironmentIn, _: AuthCtx = Depends(require_admin),
               db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    base = str(body.base_url)
    _validate_env(base, body.scan_policy)
    env = Environment(project_id=project_id, name=body.name, base_url=base, environment_type=body.environment_type,
                      scan_policy=body.scan_policy.model_dump(), authorization_confirmed=body.authorization_confirmed)
    db.add(env)
    db.flush()
    audit(db, f"environment created: {env.name} ({base})", project_id=project_id,
          metadata_json={"authorization_confirmed": body.authorization_confirmed})
    db.commit()
    return env


@router.patch("/environments/{env_id}", response_model=EnvironmentOut)
def patch_env(env_id: uuid.UUID, body: EnvironmentPatch, _: AuthCtx = Depends(require_admin),
              db: Session = Depends(get_db)):
    env = get_or_404(db, Environment, env_id)
    data = body.model_dump(exclude_unset=True, mode="json")
    if "scan_policy" in data or "base_url" in data:
        _validate_env(data.get("base_url", env.base_url), ScanPolicy(**data.get("scan_policy", env.scan_policy)))
    for k, v in data.items():
        setattr(env, k, v)
    audit(db, "environment updated", project_id=env.project_id, metadata_json=data)
    db.commit()
    return env


@router.delete("/environments/{env_id}", status_code=204)
def delete_env(env_id: uuid.UUID, _: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Environment, env_id))
    db.commit()


# ---------------- target-app login profile ----------------

def _profile(db: Session, env_id: uuid.UUID) -> AuthProfile | None:
    return db.scalars(select(AuthProfile).where(AuthProfile.environment_id == env_id)).first()


@router.get("/environments/{env_id}/auth-profile", response_model=AuthProfileOut | None)
def get_auth_profile(env_id: uuid.UUID, db: Session = Depends(get_db)):
    return _profile(db, env_id)


@router.put("/environments/{env_id}/auth-profile", response_model=AuthProfileOut)
def put_auth_profile(env_id: uuid.UUID, body: AuthProfileIn, _: AuthCtx = Depends(require_admin),
                     db: Session = Depends(get_db)):
    env = get_or_404(db, Environment, env_id)
    try:
        check_url(body.login_url, env.base_url, ScanPolicy(**env.scan_policy))
    except ScopeError as e:
        raise HTTPException(422, f"login URL rejected by scope policy: {e}")
    prof = _profile(db, env_id)
    if not prof and not body.password:
        raise HTTPException(422, "password is required for a new login profile")
    fields = body.model_dump(exclude={"password"})
    try:
        secret = encrypt(body.password) if body.password else None
    except CredentialError as e:
        raise HTTPException(409, str(e))
    if prof:
        for k, v in fields.items():
            setattr(prof, k, v)
        if secret:
            prof.password_encrypted = secret
    else:
        prof = AuthProfile(project_id=env.project_id, environment_id=env.id, password_encrypted=secret, **fields)
        db.add(prof)
    audit(db, f"login profile saved for {env.name} (user {body.username}; password "
              f"{'changed' if secret else 'unchanged'})", project_id=env.project_id)
    db.commit()
    return prof


@router.delete("/environments/{env_id}/auth-profile", status_code=204)
def delete_auth_profile(env_id: uuid.UUID, _: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    if prof := _profile(db, env_id):
        db.delete(prof)
        audit(db, "login profile removed", project_id=prof.project_id)
        db.commit()


@router.post("/environments/{env_id}/auth-profile/test")
def test_auth_profile(env_id: uuid.UUID, _: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    """Signs in once with a real browser and reports the outcome; the session is discarded."""
    env = get_or_404(db, Environment, env_id)
    prof = _profile(db, env_id)
    if not prof:
        raise HTTPException(404, "no login profile for this environment")
    policy = ScanPolicy(**env.scan_policy)
    try:
        with isolated_page(env.base_url, policy) as (page, _ctx, _events):
            final = login(page, prof, decrypt(prof.password_encrypted), env.base_url, policy)
        return {"ok": True, "message": f"Signed in; landed on {urlsplit(final).path}"}
    except (LoginFailed, CredentialError, ScopeError) as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:  # browser/network trouble
        return {"ok": False, "message": f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"}


# ---------------- discovery ----------------

@router.post("/projects/{project_id}/discovery", response_model=ScanRunOut, status_code=202)
def start_discovery(project_id: uuid.UUID, body: DiscoveryIn, db: Session = Depends(get_db)):
    from app.worker import discovery_task

    env = get_or_404(db, Environment, body.environment_id)
    if env.project_id != project_id:
        raise HTTPException(404, "Environment not found")
    if not env.authorization_confirmed:
        raise HTTPException(409, "Confirm you are authorized to test this environment before scanning (§29.1)")
    if env.status != "active":
        raise HTTPException(409, "Environment is disabled")
    policy = ScanPolicy(**env.scan_policy)
    _validate_env(env.base_url, policy)
    scan = ScanRun(project_id=project_id, environment_id=env.id, scan_policy_snapshot=policy.model_dump())
    db.add(scan)
    db.flush()
    audit(db, f"discovery started on {env.base_url}", project_id=project_id, scan_run_id=scan.id,
          metadata_json={"policy": policy.model_dump()})
    db.commit()
    discovery_task.delay(str(scan.id))
    db.refresh(scan)
    return scan


@router.get("/projects/{project_id}/scans", response_model=list[ScanRunOut])
def list_scans(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(ScanRun).where(ScanRun.project_id == project_id).order_by(ScanRun.created_at.desc())).all()


@router.get("/discovery/{scan_id}", response_model=ScanRunOut)
def get_scan(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, ScanRun, scan_id)


@router.get("/discovery/{scan_id}/pages", response_model=list[PageOut])
def scan_pages(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(DiscoveredPage).where(DiscoveredPage.scan_run_id == scan_id)
                      .options(selectinload(DiscoveredPage.elements), selectinload(DiscoveredPage.forms))
                      .order_by(DiscoveredPage.depth, DiscoveredPage.created_at)).all()


@router.get("/discovery/{scan_id}/map")
def scan_map(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models import OPEN_FINDING_STATUSES, Finding

    scan = get_or_404(db, ScanRun, scan_id)
    pages = db.scalars(select(DiscoveredPage).where(DiscoveredPage.scan_run_id == scan_id)).all()
    edges = db.scalars(select(ApplicationEdge).where(ApplicationEdge.scan_run_id == scan_id)).all()
    # Coverage overlays (§8.5): tests and open findings per page path, across the project.
    path = lambda u: urlsplit(u).path.rstrip("/") or "/"
    tests = Counter(path(t.definition_json["target_url"]) for t in db.scalars(
        select(TestCase).where(TestCase.project_id == scan.project_id,
                               TestCase.status.notin_(("rejected", "blocked")))).all())
    bugs = Counter(path(f.page_url) for f in db.scalars(
        select(Finding).where(Finding.project_id == scan.project_id,
                              Finding.status.in_(OPEN_FINDING_STATUSES))).all())
    return {"nodes": [{"id": str(p.id), "url": p.url, "title": p.title, "depth": p.depth,
                       "parent_id": str(p.parent_page_id) if p.parent_page_id else None,
                       "screenshot_artifact_id": str(p.screenshot_artifact_id) if p.screenshot_artifact_id else None,
                       "tests": tests[path(p.url)], "open_findings": bugs[path(p.url)]} for p in pages],
            "edges": [{"source": str(e.source_page_id), "target": str(e.destination_page_id), "trigger": e.trigger}
                      for e in edges]}


@router.get("/discovery/{scan_id}/logs")
def scan_logs(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.scan_run_id == scan_id).order_by(AuditLog.created_at)).all()
    return [{"severity": r.severity, "source": r.source, "message": r.message, "created_at": r.created_at} for r in rows]


@router.post("/discovery/{scan_id}/stop", response_model=ScanRunOut)
def stop_scan(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    scan = get_or_404(db, ScanRun, scan_id)
    if scan.status in ("queued", "running"):
        scan.cancel_requested = True
        if scan.status == "queued":
            scan.status = "cancelled"
        db.commit()
    return scan


# ---------------- test cases ----------------

@router.post("/projects/{project_id}/tests/generate")
def generate(project_id: uuid.UUID, body: GenerateTestsIn, db: Session = Depends(get_db)):
    scan = get_or_404(db, ScanRun, body.scan_run_id)
    if scan.project_id != project_id:
        raise HTTPException(404, "ScanRun not found")
    if scan.status != "completed":
        raise HTTPException(409, "Discovery must complete before generating tests")
    try:
        return generate_tests(db, scan, body.goals, body.use_ai)
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/projects/{project_id}/test-cases", response_model=list[TestCaseOut])
def list_tests(project_id: uuid.UUID, status: str | None = None, db: Session = Depends(get_db)):
    q = select(TestCase).where(TestCase.project_id == project_id)
    if status:
        q = q.where(TestCase.status == status)
    return db.scalars(q.order_by(TestCase.created_at, TestCase.key)).all()


@router.get("/test-cases/{tc_id}", response_model=TestCaseOut)
def get_test(tc_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, TestCase, tc_id)


def _test_env(db: Session, tc: TestCase) -> Environment:
    scan = db.get(ScanRun, tc.scan_run_id) if tc.scan_run_id else None
    if not scan:
        raise HTTPException(409, "test has no source scan/environment")
    return db.get(Environment, scan.environment_id)


@router.patch("/test-cases/{tc_id}", response_model=TestCaseOut)
def edit_test(tc_id: uuid.UUID, body: TestCasePatch, db: Session = Depends(get_db)):
    """Editing re-validates and returns the test to draft: edited tests need re-approval."""
    tc = get_or_404(db, TestCase, tc_id)
    env = _test_env(db, tc)
    set_definition(db, tc, body.definition, env.base_url, ScanPolicy(**env.scan_policy), "edited", actor=actor(db))
    db.commit()
    return tc


@router.get("/test-cases/{tc_id}/versions", response_model=list[TestCaseVersionOut])
def test_versions(tc_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(TestCaseVersion).where(TestCaseVersion.test_case_id == tc_id)
                      .order_by(TestCaseVersion.version.desc())).all()


@router.post("/test-cases/{tc_id}/duplicate", response_model=TestCaseOut, status_code=201)
def duplicate_test(tc_id: uuid.UUID, db: Session = Depends(get_db)):
    src = get_or_404(db, TestCase, tc_id)
    env = _test_env(db, src)
    d = TestCaseDef(**src.definition_json)
    d.key, d.title = f"{d.key}-COPY"[:60], f"{d.title} (copy)"
    tc = TestCase(project_id=src.project_id, scan_run_id=src.scan_run_id, generated_by=src.generated_by, version=0)
    db.add(tc)
    set_definition(db, tc, d, env.base_url, ScanPolicy(**env.scan_policy), f"duplicated:{src.key}", actor=actor(db))
    db.commit()
    return tc


@router.post("/test-cases/{tc_id}/regenerate", response_model=TestCaseOut)
def regenerate(tc_id: uuid.UUID, body: RegenerateIn, db: Session = Depends(get_db)):
    tc = get_or_404(db, TestCase, tc_id)
    try:
        regenerate_test(db, tc, body.instructions)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(502, f"AI regeneration failed: {type(e).__name__}")
    db.commit()
    return tc


def _set_status(db, tc_id, status, allowed_from):
    tc = get_or_404(db, TestCase, tc_id)
    if tc.status not in allowed_from:
        raise HTTPException(409, f"cannot move test from {tc.status} to {status}")
    tc.status = status
    audit(db, f"test {tc.key} → {status}", project_id=tc.project_id)
    db.commit()
    return tc


@router.post("/test-cases/{tc_id}/approve", response_model=TestCaseOut)
def approve(tc_id: uuid.UUID, db: Session = Depends(get_db)):
    return _set_status(db, tc_id, "approved", {"draft", "disabled", "rejected"})


@router.post("/test-cases/{tc_id}/reject", response_model=TestCaseOut)
def reject(tc_id: uuid.UUID, db: Session = Depends(get_db)):
    return _set_status(db, tc_id, "rejected", {"draft", "approved", "blocked"})


@router.post("/test-cases/{tc_id}/disable", response_model=TestCaseOut)
def disable(tc_id: uuid.UUID, db: Session = Depends(get_db)):
    return _set_status(db, tc_id, "disabled", {"draft", "approved"})


# ---------------- execution ----------------

def _start_run(db, project_id, env_id, tc_ids, retest_finding_id=None) -> TestRun:
    from app.worker import test_run_task

    run = TestRun(project_id=project_id, environment_id=env_id, retest_finding_id=retest_finding_id)
    db.add(run)
    db.flush()
    audit(db, f"test run started ({len(tc_ids)} tests)", project_id=project_id, test_run_id=run.id)
    db.commit()
    test_run_task.delay(str(run.id), [str(i) for i in tc_ids])
    db.refresh(run)
    return run


@router.post("/test-runs", response_model=TestRunOut, status_code=202)
def create_run(body: TestRunIn, db: Session = Depends(get_db)):
    env = get_or_404(db, Environment, body.environment_id)
    if not env.authorization_confirmed:
        raise HTTPException(409, "Environment authorization not confirmed")
    tcs = db.scalars(select(TestCase).where(TestCase.id.in_(body.test_case_ids))).all()
    if len(tcs) != len(set(body.test_case_ids)) or any(t.project_id != env.project_id for t in tcs):
        raise HTTPException(404, "Unknown test case for this project")
    if bad := [t.key for t in tcs if t.status != "approved"]:
        raise HTTPException(409, f"Only approved tests can run; not approved: {', '.join(bad)}")
    return _start_run(db, env.project_id, env.id, body.test_case_ids)


@router.get("/projects/{project_id}/test-runs", response_model=list[TestRunOut])
def list_runs(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())).all()


@router.get("/test-runs/{run_id}", response_model=TestRunDetailOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_or_404(db, TestRun, run_id)


@router.post("/test-runs/{run_id}/cancel", response_model=TestRunOut)
def cancel_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = get_or_404(db, TestRun, run_id)
    if run.status in ("queued", "running"):
        run.cancel_requested = True
        db.commit()
    return run


@router.get("/test-executions/{ex_id}", response_model=ExecutionDetailOut)
def get_execution(ex_id: uuid.UUID, db: Session = Depends(get_db)):
    ex = get_or_404(db, TestExecution, ex_id)
    arts = db.scalars(select(Artifact).where(Artifact.test_execution_id == ex.id)).all()
    return ExecutionDetailOut.model_validate(ex).model_copy(
        update={"artifacts": [ArtifactOut.model_validate(a) for a in arts]})


@router.post("/test-executions/{ex_id}/rerun", response_model=TestRunOut, status_code=202)
def rerun(ex_id: uuid.UUID, db: Session = Depends(get_db)):
    ex = get_or_404(db, TestExecution, ex_id)
    run = db.get(TestRun, ex.test_run_id)
    tc = db.get(TestCase, ex.test_case_id)
    if tc.status != "approved":
        raise HTTPException(409, "Test is no longer approved")
    return _start_run(db, run.project_id, run.environment_id, [tc.id])


# ---------------- artifacts ----------------

@router.get("/artifacts/{art_id}")
def get_artifact(art_id: uuid.UUID, db: Session = Depends(get_db)):
    art = get_or_404(db, Artifact, art_id)
    path = storage.path_for(art)
    if not path.exists():
        raise HTTPException(410, "Artifact file is missing (expired or deleted)")
    return FileResponse(path, media_type=art.mime_type)
