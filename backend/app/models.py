"""Database models for Milestones A–C (projects → discovery → tests → executions → artifacts).

Auth/orgs, findings, tickets and retests arrive in later phases.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONType


def now():
    return datetime.now(UTC)


def pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def fk(target, **kw):
    return mapped_column(Uuid, ForeignKey(target, ondelete="CASCADE"), index=True, **kw)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


ROLES = ("viewer", "member", "admin", "owner")  # ascending privilege


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-case
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))  # scrypt$n$r$p$salt$hash
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_member_org_user"),)
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    role: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class UserSession(Base):
    """Server-side session: the cookie holds a random token; only its SHA-256 is stored (revocable)."""

    __tablename__ = "user_sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Project(Timestamps, Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = pk()
    # NULL only for projects created before accounts existed; the first registered org claims them.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE", name="fk_projects_organization_id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    repository_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    environments: Mapped[list["Environment"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class Environment(Timestamps, Base):
    __tablename__ = "environments"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    environment_type: Mapped[str] = mapped_column(String(20), default="staging")
    # Validated by schemas.ScanPolicy; snapshotted into every scan run.
    scan_policy: Mapped[dict] = mapped_column(JSONType)
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")


class AuthProfile(Timestamps, Base):
    """How to sign in to the app under test (§7.2, §22 auth_profiles). One per environment.
    The password is Fernet-encrypted; it is decrypted only to type it into the login form."""

    __tablename__ = "auth_profiles"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    environment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("environments.id", ondelete="CASCADE"),
                                                      unique=True)
    login_url: Mapped[str] = mapped_column(String(2000))
    username: Mapped[str] = mapped_column(String(320))
    password_encrypted: Mapped[str] = mapped_column(Text)
    username_selector: Mapped[str] = mapped_column(String(300), default="")
    password_selector: Mapped[str] = mapped_column(String(300), default="")
    submit_selector: Mapped[str] = mapped_column(String(300), default="")
    success_url_contains: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ScanRun(Base):
    __tablename__ = "scan_runs"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    environment_id: Mapped[uuid.UUID] = fk("environments.id")
    scan_policy_snapshot: Mapped[dict] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiscoveredPage(Base):
    __tablename__ = "discovered_pages"
    id: Mapped[uuid.UUID] = pk()
    scan_run_id: Mapped[uuid.UUID] = fk("scan_runs.id")
    parent_page_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("discovered_pages.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(String(2000))
    route_pattern: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(500), default="")
    status_code: Mapped[int | None] = mapped_column(Integer)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    discovery_source: Mapped[str] = mapped_column(String(40), default="link")
    screenshot_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    elements: Mapped[list["DiscoveredElement"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    forms: Mapped[list["DiscoveredForm"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class DiscoveredElement(Base):
    __tablename__ = "discovered_elements"
    id: Mapped[uuid.UUID] = pk()
    discovered_page_id: Mapped[uuid.UUID] = fk("discovered_pages.id")
    element_type: Mapped[str] = mapped_column(String(40))
    accessible_name: Mapped[str] = mapped_column(String(500), default="")
    selector_candidates_json: Mapped[list] = mapped_column(JSONType, default=list)
    attributes_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)


class DiscoveredForm(Base):
    __tablename__ = "discovered_forms"
    id: Mapped[uuid.UUID] = pk()
    discovered_page_id: Mapped[uuid.UUID] = fk("discovered_pages.id")
    name: Mapped[str] = mapped_column(String(200), default="")
    method: Mapped[str] = mapped_column(String(10), default="get")
    action: Mapped[str] = mapped_column(String(2000), default="")
    fields_json: Mapped[list] = mapped_column(JSONType, default=list)
    submit_label: Mapped[str] = mapped_column(String(200), default="")


class ApplicationEdge(Base):
    __tablename__ = "application_edges"
    id: Mapped[uuid.UUID] = pk()
    scan_run_id: Mapped[uuid.UUID] = fk("scan_runs.id")
    source_page_id: Mapped[uuid.UUID] = fk("discovered_pages.id")
    destination_page_id: Mapped[uuid.UUID] = fk("discovered_pages.id")
    edge_type: Mapped[str] = mapped_column(String(30), default="navigation")
    trigger: Mapped[str] = mapped_column(String(500), default="")


class DiscoveredEndpoint(Base):
    """API endpoint inventory (§11.2), deduplicated per environment + method + path template."""

    __tablename__ = "discovered_endpoints"
    __table_args__ = (UniqueConstraint("environment_id", "method", "path", name="uq_endpoint_env_method_path"),)
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    environment_id: Mapped[uuid.UUID] = fk("environments.id")
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(1000))  # template, e.g. /api/users/{user_id}
    operation_id: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(String(500), default="")
    parameters_json: Mapped[list] = mapped_column(JSONType, default=list)
    has_request_body: Mapped[bool] = mapped_column(Boolean, default=False)
    response_content_type: Mapped[str] = mapped_column(String(100), default="")
    response_schema_json: Mapped[dict | None] = mapped_column(JSONType)  # 2xx schema with components for $ref
    source: Mapped[str] = mapped_column(String(20))  # openapi | network
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)  # from OpenAPI `security`
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TestCase(Timestamps, Base):
    __tablename__ = "test_cases"
    __test__ = False  # not a pytest class
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    scan_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("scan_runs.id", ondelete="SET NULL"))
    key: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[str] = mapped_column(String(5))
    definition_json: Mapped[dict] = mapped_column(JSONType)  # schemas.TestCaseDef
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # duplicate detection
    # draft → approved | rejected | disabled ; blocked = failed validation
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    validation_errors_json: Mapped[list] = mapped_column(JSONType, default=list)
    generated_by: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)


class TestCaseVersion(Base):
    """Immutable history of every test definition (§24 test_case_versions)."""

    __tablename__ = "test_case_versions"
    __test__ = False
    id: Mapped[uuid.UUID] = pk()
    test_case_id: Mapped[uuid.UUID] = fk("test_cases.id")
    version: Mapped[int] = mapped_column(Integer)
    definition_json: Mapped[dict] = mapped_column(JSONType)
    source: Mapped[str] = mapped_column(String(80))  # generated:<by> | edited | regenerated:<by> | duplicated
    created_by: Mapped[str] = mapped_column(String(100), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TestRun(Base):
    __tablename__ = "test_runs"
    __test__ = False
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    environment_id: Mapped[uuid.UUID] = fk("environments.id")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    browser: Mapped[str] = mapped_column(String(20), default="chromium")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set when this run verifies a fix (§16); retest history = runs with this id.
    retest_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("findings.id", ondelete="SET NULL", use_alter=True, name="fk_test_runs_retest_finding_id"),
        index=True)
    summary_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executions: Mapped[list["TestExecution"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class TestExecution(Base):
    __tablename__ = "test_executions"
    __test__ = False
    id: Mapped[uuid.UUID] = pk()
    test_run_id: Mapped[uuid.UUID] = fk("test_runs.id")
    test_case_id: Mapped[uuid.UUID] = fk("test_cases.id")
    test_case_version: Mapped[int] = mapped_column(Integer)
    definition_snapshot: Mapped[dict] = mapped_column(JSONType)
    # queued, running, passed, failed, blocked, skipped, timed_out, cancelled, inconclusive
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    failure_type: Mapped[str | None] = mapped_column(String(40))  # assertion | step_error | scope | infrastructure | timeout
    failure_message: Mapped[str | None] = mapped_column(Text)
    assertion_results_json: Mapped[list] = mapped_column(JSONType, default=list)
    execution_metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    steps: Mapped[list["ExecutionStep"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="ExecutionStep.step_number"
    )


class ExecutionStep(Base):
    __tablename__ = "execution_steps"
    id: Mapped[uuid.UUID] = pk()
    test_execution_id: Mapped[uuid.UUID] = fk("test_executions.id")
    step_number: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[str] = mapped_column(String(30))
    action_definition_json: Mapped[dict] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(20))  # passed | failed | skipped
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    screenshot_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    result_json: Mapped[dict | None] = mapped_column(JSONType)  # HTTP steps: sanitized request/response evidence


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    scan_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("scan_runs.id", ondelete="CASCADE"), index=True)
    test_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("test_executions.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(30))  # screenshot | trace
    storage_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    redaction_status: Mapped[str] = mapped_column(String(30), default="password_fields_masked")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    """Audit trail (§29.7): scan starts, blocked actions, config changes."""

    __tablename__ = "logs"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    scan_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    test_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    severity: Mapped[str] = mapped_column(String(10), default="info")
    source: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(320), default="system")  # who did it (§29.7)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


# ---------------- Milestones D–F: findings, tickets, retest ----------------

FINDING_STATUSES = ("new", "triaged", "assigned", "in_progress", "fixed", "ready_for_retest", "verified",
                    "reopened", "wont_fix", "duplicate", "false_positive")
OPEN_FINDING_STATUSES = ("new", "triaged", "assigned", "in_progress", "fixed", "ready_for_retest", "reopened")


class Finding(Timestamps, Base):
    __tablename__ = "findings"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    environment_id: Mapped[uuid.UUID] = fk("environments.id")
    test_case_id: Mapped[uuid.UUID] = fk("test_cases.id")
    test_execution_id: Mapped[uuid.UUID] = fk("test_executions.id")  # first detection (original evidence)
    last_execution_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_executions.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # same test + same failing step = same finding
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(30))
    page_url: Mapped[str] = mapped_column(String(2000))
    severity: Mapped[str] = mapped_column(String(10), index=True)  # critical | high | medium | low | info
    confidence: Mapped[str] = mapped_column(String(15))  # confirmed | probable | potential (§12.4)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    expected_result: Mapped[str] = mapped_column(Text, default="")
    actual_result: Mapped[str] = mapped_column(Text, default="")
    reproduction_steps_json: Mapped[list] = mapped_column(JSONType, default=list)
    ai_analysis_json: Mapped[dict | None] = mapped_column(JSONType)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("findings.id", ondelete="SET NULL"))
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Developer(Base):
    """A configured assignee (§15.3). Becomes a real user account once auth lands."""

    __tablename__ = "developers"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), default="")
    team: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Ticket(Timestamps, Base):
    """Internal ticket (§15). Its status is the linked finding's lifecycle status, so the two never disagree."""

    __tablename__ = "tickets"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("findings.id", ondelete="CASCADE"), unique=True)
    number: Mapped[int] = mapped_column(Integer)  # per-project human id, e.g. TP-3
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)  # generated bug report (markdown)
    severity: Mapped[str] = mapped_column(String(10))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("developers.id", ondelete="SET NULL"))
    external_provider: Mapped[str | None] = mapped_column(String(20))
    external_issue_url: Mapped[str | None] = mapped_column(String(500))


class FindingEvent(Base):
    """History for a finding and its ticket: status changes, comments, assignment, retests (§14.4, §39)."""

    __tablename__ = "finding_events"
    id: Mapped[uuid.UUID] = pk()
    finding_id: Mapped[uuid.UUID] = fk("findings.id")
    actor: Mapped[str] = mapped_column(String(100), default="system")
    event_type: Mapped[str] = mapped_column(String(30))  # detected, redetected, status, severity, comment, ticket, assigned, retest
    message: Mapped[str] = mapped_column(Text, default="")
    data_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
