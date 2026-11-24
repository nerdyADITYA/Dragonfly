"""Platform authentication and authorization (§27.1, Phase 1).

- Passwords: stdlib scrypt. Sessions: random token in an HttpOnly cookie, SHA-256 stored server-side.
- Every API request goes through `authenticate`: it resolves the session, enforces the role by HTTP
  method, and checks that every id in the URL belongs to the caller's organization (404 otherwise, so
  other tenants' ids are indistinguishable from missing ones). `routes.get_or_404` repeats the
  organization check for ids that arrive in request bodies.
"""
import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
    ROLES,
    Artifact,
    AuditLog,
    Developer,
    Environment,
    Finding,
    Organization,
    OrganizationMember,
    Project,
    ScanRun,
    TestCase,
    TestExecution,
    TestRun,
    Ticket,
    User,
    UserSession,
)

COOKIE = "df_session"
MIN_PASSWORD = 10
SCRYPT = (2**14, 8, 1)


# ---------------- passwords ----------------

def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = SCRYPT
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), dk)


_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


# ---------------- login throttling ----------------
# shortcut: in-process counters (per API replica); move to Redis when running several API processes.
_failures: dict[str, list[float]] = defaultdict(list)
WINDOW = 15 * 60
MAX_FAILURES = {"email": 5, "ip": 30}  # per account; per IP is looser so one office NAT is not locked out


def _throttled(key: str) -> bool:
    now = time.monotonic()
    _failures[key] = [t for t in _failures[key] if now - t < WINDOW]
    return len(_failures[key]) >= MAX_FAILURES[key.split(":", 1)[0]]


# ---------------- sessions & context ----------------

@dataclass
class AuthCtx:
    user: User
    org_id: uuid.UUID
    role: str

    def at_least(self, role: str) -> bool:
        return ROLES.index(self.role) >= ROLES.index(role)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def resolve(db: Session, token: str | None) -> AuthCtx | None:
    if not token:
        return None
    s = db.scalars(select(UserSession).where(UserSession.token_hash == _token_hash(token))).first()
    if not s or s.expires_at.replace(tzinfo=s.expires_at.tzinfo or UTC) < datetime.now(UTC):
        return None
    user = db.get(User, s.user_id)
    m = db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)
                   .order_by(OrganizationMember.created_at)).first()
    return AuthCtx(user, m.organization_id, m.role) if user and m else None


def _start_session(db: Session, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token_hash=_token_hash(token),
                       expires_at=datetime.now(UTC) + timedelta(days=settings.session_days)))
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
                        max_age=settings.session_days * 86400)


def project_of(db: Session, obj) -> Project | None:
    if isinstance(obj, Project):
        return obj
    pid = getattr(obj, "project_id", None)
    if pid is None and isinstance(obj, TestExecution):
        pid = db.get(TestRun, obj.test_run_id).project_id
    return db.get(Project, pid) if pid else None


def can_access(db: Session, obj) -> bool:
    ctx: AuthCtx | None = db.info.get("auth")
    if ctx is None:
        return False
    project = project_of(db, obj)
    return project is not None and project.organization_id == ctx.org_id


def actor(db: Session) -> str:
    ctx = db.info.get("auth")
    return ctx.user.email if ctx else "system"


# Path parameter name → model, so every id in a URL is tenant-checked before the route runs.
PATH_MODELS = {"project_id": Project, "env_id": Environment, "scan_id": ScanRun, "tc_id": TestCase,
               "run_id": TestRun, "ex_id": TestExecution, "finding_id": Finding, "ticket_id": Ticket,
               "dev_id": Developer, "art_id": Artifact}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _same_origin(request: Request) -> bool:
    """CSRF guard for state-changing requests: a present Origin must be this site or an allowed origin."""
    origin = request.headers.get("origin")
    if not origin:
        return True  # non-browser clients; SameSite=Lax already keeps cross-site forms from sending the cookie
    host = urlsplit(origin).netloc
    return host == request.headers.get("host") or origin in settings.cors_origins


def authenticate(request: Request, db: Session = Depends(get_db)) -> AuthCtx:
    ctx = resolve(db, request.cookies.get(COOKIE))
    if not ctx:
        raise HTTPException(401, "Sign in required")
    if request.method not in SAFE_METHODS:
        if not _same_origin(request):
            raise HTTPException(403, "Cross-site request refused")
        if not ctx.at_least("member"):
            raise HTTPException(403, "Viewers have read-only access")
    db.info["auth"] = ctx
    for name, model in PATH_MODELS.items():
        if (raw := request.path_params.get(name)) is None:
            continue
        try:
            obj = db.get(model, uuid.UUID(str(raw)))
        except ValueError:
            continue  # FastAPI's own validation returns 422
        if obj is not None and not can_access(db, obj):
            raise HTTPException(404, f"{model.__name__} not found")
    return ctx


def require_admin(ctx: AuthCtx = Depends(authenticate)) -> AuthCtx:
    if not ctx.at_least("admin"):
        raise HTTPException(403, "Admin role required")
    return ctx


def org_project_ids(db: Session, ctx: AuthCtx) -> list[uuid.UUID]:
    return list(db.scalars(select(Project.id).where(Project.organization_id == ctx.org_id)))


# ---------------- endpoints ----------------

router = APIRouter(prefix="/api/v1")


class RegisterIn(BaseModel):
    organization: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class MemberIn(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=200)
    role: str = Field(pattern="^(viewer|member|admin|owner)$")
    password: str = Field(min_length=MIN_PASSWORD, max_length=200, description="Initial password to share securely")


class RoleIn(BaseModel):
    role: str = Field(pattern="^(viewer|member|admin|owner)$")


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


def _me(ctx: AuthCtx, db: Session) -> dict:
    org = db.get(Organization, ctx.org_id)
    return {"id": ctx.user.id, "email": ctx.user.email, "display_name": ctx.user.display_name, "role": ctx.role,
            "organization": {"id": org.id, "name": org.name}}


@router.get("/auth/status")
def status(db: Session = Depends(get_db)):
    """Lets the UI decide between first-run setup and sign-in."""
    return {"setup_required": not db.scalar(select(func.count(User.id)))}


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    """First-run only: creates the organization and its owner. Later users are added by admins."""
    if db.scalar(select(func.count(User.id))):
        raise HTTPException(403, "Registration is closed; ask an admin to add you")
    org = Organization(name=body.organization)
    user = User(email=body.email.lower(), display_name=body.display_name, password_hash=hash_password(body.password))
    db.add_all([org, user])
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    claimed = db.execute(update(Project).where(Project.organization_id.is_(None))
                         .values(organization_id=org.id)).rowcount
    db.add(AuditLog(source="auth", actor=user.email, message=f"organization created; {claimed} existing projects claimed"))
    _start_session(db, user, response)
    db.commit()
    return _me(AuthCtx(user, org.id, "owner"), db)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    keys = (f"email:{email}", f"ip:{request.client.host if request.client else '?'}")
    if any(_throttled(k) for k in keys):
        raise HTTPException(429, "Too many failed sign-in attempts; try again in 15 minutes")
    user = db.scalars(select(User).where(User.email == email)).first()
    if not verify_password(body.password, user.password_hash if user else _DUMMY_HASH) or not user:
        for k in keys:
            _failures[k].append(time.monotonic())
        db.add(AuditLog(source="auth", severity="warning", actor=email, message="failed sign-in"))
        db.commit()
        raise HTTPException(401, "Email or password is incorrect")
    m = db.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)
                   .order_by(OrganizationMember.created_at)).first()
    if not m:
        raise HTTPException(403, "Your account is not a member of any organization")
    for k in keys:
        _failures.pop(k, None)
    _start_session(db, user, response)
    db.commit()
    return _me(AuthCtx(user, m.organization_id, m.role), db)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    if token := request.cookies.get(COOKIE):
        db.query(UserSession).filter(UserSession.token_hash == _token_hash(token)).delete()
        db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/auth/me")
def me(ctx: AuthCtx = Depends(authenticate), db: Session = Depends(get_db)):
    return _me(ctx, db)


@router.post("/auth/password", status_code=204)
def change_password(body: PasswordIn, ctx: AuthCtx = Depends(authenticate), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise HTTPException(403, "Current password is incorrect")
    user = db.get(User, ctx.user.id)
    user.password_hash = hash_password(body.new_password)
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()  # sign out everywhere else
    db.commit()


# ---------------- team (organization members) ----------------

@router.get("/org/members")
def members(ctx: AuthCtx = Depends(authenticate), db: Session = Depends(get_db)):
    rows = db.execute(select(OrganizationMember, User).join(User, User.id == OrganizationMember.user_id)
                      .where(OrganizationMember.organization_id == ctx.org_id).order_by(User.email)).all()
    return [{"user_id": u.id, "email": u.email, "display_name": u.display_name, "role": m.role} for m, u in rows]


@router.post("/org/members", status_code=201)
def add_member(body: MemberIn, ctx: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    if body.role == "owner" and ctx.role != "owner":
        raise HTTPException(403, "Only owners can add owners")
    if db.scalars(select(User).where(User.email == body.email.lower())).first():
        raise HTTPException(409, "A user with this email already exists")
    user = User(email=body.email.lower(), display_name=body.display_name, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(OrganizationMember(organization_id=ctx.org_id, user_id=user.id, role=body.role))
    db.add(AuditLog(source="auth", actor=ctx.user.email, message=f"added {user.email} as {body.role}"))
    db.commit()
    return {"user_id": user.id, "email": user.email, "display_name": user.display_name, "role": body.role}


def _membership(db: Session, ctx: AuthCtx, user_id: uuid.UUID) -> OrganizationMember:
    m = db.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == ctx.org_id,
                                                    OrganizationMember.user_id == user_id)).first()
    if not m:
        raise HTTPException(404, "Member not found")
    return m


def _owners(db: Session, org_id) -> int:
    return db.scalar(select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == org_id,
                                                                     OrganizationMember.role == "owner"))


@router.patch("/org/members/{user_id}")
def set_role(user_id: uuid.UUID, body: RoleIn, ctx: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    m = _membership(db, ctx, user_id)
    if "owner" in (m.role, body.role) and ctx.role != "owner":
        raise HTTPException(403, "Only owners can grant or remove the owner role")
    if m.role == "owner" and body.role != "owner" and _owners(db, ctx.org_id) == 1:
        raise HTTPException(409, "An organization needs at least one owner")
    m.role = body.role
    db.add(AuditLog(source="auth", actor=ctx.user.email, message=f"role of {user_id} set to {body.role}"))
    db.commit()
    return {"user_id": user_id, "role": m.role}


@router.delete("/org/members/{user_id}", status_code=204)
def remove_member(user_id: uuid.UUID, ctx: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)):
    if user_id == ctx.user.id:
        raise HTTPException(409, "You cannot remove yourself")
    m = _membership(db, ctx, user_id)
    if m.role == "owner" and ctx.role != "owner":
        raise HTTPException(403, "Only owners can remove owners")
    db.delete(m)
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.add(AuditLog(source="auth", actor=ctx.user.email, message=f"removed member {user_id}"))
    db.commit()
