import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ---------- Scan policy (§22 scan_policies, embedded per environment and snapshotted per scan) ----------


class ScanPolicy(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list, description="Hosts the scan may touch; '*.x.com' allows subdomains. Defaults to the base URL host.")
    excluded_paths: list[str] = Field(default_factory=list, description="Path prefixes never visited, e.g. /admin")
    allow_private_network: bool = Field(False, description="Allow targets on private/loopback IPs (local or docker demo apps).")
    max_pages: int = Field(25, ge=1, le=500)
    max_depth: int = Field(3, ge=0, le=10)
    max_duration_seconds: int = Field(300, ge=10, le=3600)
    step_timeout_ms: int = Field(10_000, ge=1000, le=60_000)
    test_timeout_seconds: int = Field(60, ge=5, le=600)
    destructive_actions_allowed: bool = False
    security_profile: Literal["off", "passive", "standard"] = Field(
        "passive", description="passive: read-only header/config checks; standard: adds low-volume probes such as a failed login")
    requests_per_second: float = Field(5, gt=0, le=50, description="Rate limit for HTTP/API/security requests")
    max_requests: int = Field(200, ge=1, le=10_000, description="Request budget per test run (HTTP tests)")
    viewport_width: int = 1280
    viewport_height: int = 800


# ---------- Projects / environments ----------


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    repository_url: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    repository_url: str | None = None
    status: Literal["active", "archived"] | None = None


class ProjectOut(ORM):
    id: uuid.UUID
    name: str
    description: str
    repository_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class EnvironmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: HttpUrl
    environment_type: Literal["local", "development", "qa", "staging", "production"] = "staging"
    scan_policy: ScanPolicy = Field(default_factory=ScanPolicy)
    authorization_confirmed: bool = Field(False, description="User confirms they are authorized to test this target (§29.1).")


class EnvironmentPatch(BaseModel):
    name: str | None = None
    base_url: HttpUrl | None = None
    environment_type: Literal["local", "development", "qa", "staging", "production"] | None = None
    scan_policy: ScanPolicy | None = None
    authorization_confirmed: bool | None = None
    status: Literal["active", "disabled"] | None = None


class EnvironmentOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    base_url: str
    environment_type: str
    scan_policy: dict
    authorization_confirmed: bool
    status: str
    created_at: datetime


# ---------- Test case & action schema (§9.4, §10.3) ----------
# Flat action model: simple for an LLM to emit under structured outputs; per-type
# required fields are enforced by validator.REQUIRED_FIELDS.

ActionType = Literal[
    "navigate", "click", "fill", "select", "check", "uncheck", "press", "hover", "wait_for", "screenshot",
    "assert_text", "assert_visible", "assert_hidden", "assert_url", "assert_title", "assert_value", "assert_count",
    "assert_no_page_errors",
    # HTTP / API / security (no browser): a test whose first step is api_request uses only these.
    "api_request", "assert_status", "assert_json_schema", "assert_header", "assert_header_not", "assert_body_not",
    "assert_cookies_secure",
]


class Target(BaseModel):
    """How to find an element. Resolved in the plan's selector priority order (§21.3)."""

    role: str | None = Field(None, description="ARIA role, e.g. button, link, textbox, heading")
    name: str | None = Field(None, description="Accessible name used with role")
    label: str | None = None
    placeholder: str | None = None
    test_id: str | None = None
    text: str | None = None
    css: str | None = Field(None, description="Last resort CSS selector")


class Action(BaseModel):
    type: ActionType
    target: Target | None = None
    url: str | None = Field(None, description="navigate: absolute URL inside scope")
    value: str | None = Field(None, description="fill/select value, assert_value expected value, or assert_url/assert_title substring")
    key: str | None = Field(None, description="press: key name, e.g. Enter")
    text: str | None = Field(None, description="assert_text: expected text (substring)")
    count: int | None = Field(None, description="assert_count: expected number of matches")
    method: str | None = Field(None, description="api_request: HTTP method")
    headers: str | None = Field(None, description="api_request: extra request headers as a JSON object string")
    body: str | None = Field(None, description="api_request: body as a JSON string; `value` = json|form selects the encoding")
    json_schema: str | None = Field(None, description="assert_json_schema: JSON Schema as a JSON string")
    description: str = Field("", description="Human-readable step description")


class TestCaseDef(BaseModel):
    __test__ = False
    key: str = Field(description="Short unique ID like LOGIN-FUNC-001")
    title: str
    description: str = ""
    category: Literal["functional", "validation", "edge_case", "regression", "accessibility", "api", "security"]
    priority: Literal["P0", "P1", "P2", "P3"]
    risk: Literal["low", "medium", "high"] = "medium"
    preconditions: list[str] = Field(default_factory=list)
    target_url: str
    steps: list[Action]
    expected_outcomes: list[str] = Field(default_factory=list)
    data_requirements: list[str] = Field(default_factory=list)
    side_effect: Literal["none", "writes_data", "destructive"] = Field(
        "none", description="none = read-only; writes_data = submits forms; destructive = deletes/sends/pays"
    )
    confidence: float = Field(0.7, ge=0, le=1)
    source_observations: list[str] = Field(default_factory=list, description="Which discovered pages/forms motivated this test")


class TestPlan(BaseModel):
    __test__ = False
    tests: list[TestCaseDef]


class TestCaseOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    scan_run_id: uuid.UUID | None
    key: str
    title: str
    category: str
    priority: str
    definition_json: dict
    status: str
    validation_errors_json: list
    generated_by: str
    version: int
    created_at: datetime
    updated_at: datetime


class TestCasePatch(BaseModel):
    definition: TestCaseDef


class GenerateTestsIn(BaseModel):
    scan_run_id: uuid.UUID
    goals: str = Field("", max_length=2000, description="Optional user testing goals passed to the AI planner")
    use_ai: bool = True


# ---------- Scans / discovery ----------


class DiscoveryIn(BaseModel):
    environment_id: uuid.UUID


class ScanRunOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    environment_id: uuid.UUID
    status: str
    stage: str
    scan_policy_snapshot: dict
    summary_json: dict
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ElementOut(ORM):
    id: uuid.UUID
    element_type: str
    accessible_name: str
    selector_candidates_json: list
    attributes_json: dict
    is_visible: bool


class FormOut(ORM):
    id: uuid.UUID
    name: str
    method: str
    action: str
    fields_json: list
    submit_label: str


class PageOut(ORM):
    id: uuid.UUID
    parent_page_id: uuid.UUID | None
    url: str
    route_pattern: str
    title: str
    status_code: int | None
    depth: int
    screenshot_artifact_id: uuid.UUID | None
    elements: list[ElementOut]
    forms: list[FormOut]


# ---------- Execution ----------


class TestRunIn(BaseModel):
    __test__ = False
    environment_id: uuid.UUID
    test_case_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class StepOut(ORM):
    result_json: dict | None = None
    step_number: int
    action_type: str
    action_definition_json: dict
    status: str
    duration_ms: int
    error_message: str | None
    screenshot_artifact_id: uuid.UUID | None


class ArtifactOut(ORM):
    id: uuid.UUID
    artifact_type: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class ExecutionOut(ORM):
    id: uuid.UUID
    test_run_id: uuid.UUID
    test_case_id: uuid.UUID
    test_case_version: int
    definition_snapshot: dict
    status: str
    attempt_number: int
    failure_type: str | None
    failure_message: str | None
    assertion_results_json: list
    execution_metadata_json: dict
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None


class ExecutionDetailOut(ExecutionOut):
    steps: list[StepOut]
    artifacts: list[ArtifactOut] = []


class TestRunOut(ORM):
    __test__ = False
    id: uuid.UUID
    project_id: uuid.UUID
    environment_id: uuid.UUID
    status: str
    browser: str
    retest_finding_id: uuid.UUID | None = None
    summary_json: dict
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TestRunDetailOut(TestRunOut):
    executions: list[ExecutionOut]


# ---------- Findings, tickets, retest (Milestones D–F) ----------

Severity = Literal["critical", "high", "medium", "low", "info"]


class FindingOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    environment_id: uuid.UUID
    test_case_id: uuid.UUID
    test_execution_id: uuid.UUID
    last_execution_id: uuid.UUID
    title: str
    description: str
    category: str
    page_url: str
    severity: str
    confidence: str
    status: str
    expected_result: str
    actual_result: str
    reproduction_steps_json: list
    ai_analysis_json: dict | None
    occurrences: int
    duplicate_of_id: uuid.UUID | None
    first_detected_at: datetime
    last_detected_at: datetime
    updated_at: datetime


class FindingEventOut(ORM):
    actor: str
    event_type: str
    message: str
    data_json: dict
    created_at: datetime


class DeveloperIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field("", max_length=320)
    team: str = Field("", max_length=100)


class DeveloperOut(ORM):
    id: uuid.UUID
    name: str
    email: str
    team: str


class TicketOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    finding_id: uuid.UUID
    number: int
    title: str
    description: str
    severity: str
    assignee_id: uuid.UUID | None
    external_issue_url: str | None
    created_at: datetime
    updated_at: datetime
    status: str = ""  # the finding's lifecycle status
    assignee: DeveloperOut | None = None


class FindingDetailOut(FindingOut):
    events: list[FindingEventOut]
    ticket: TicketOut | None
    retest_runs: list[TestRunDetailOut]
    duplicate_candidates: list[FindingOut]
    original_screenshot_id: uuid.UUID | None
    latest_screenshot_id: uuid.UUID | None
    http_evidence: dict | None = None  # HTTP tests: sanitized request/response of the failing step


class FindingPatch(BaseModel):
    status: str | None = None
    severity: Severity | None = None
    reason: str = Field("", max_length=2000, description="Required for a severity override; optional note for status")


class DuplicateIn(BaseModel):
    duplicate_of_id: uuid.UUID


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class TicketIn(BaseModel):
    assignee_id: uuid.UUID | None = None


class AssignIn(BaseModel):
    developer_id: uuid.UUID


class RetestIn(BaseModel):
    include_related: bool = Field(False, description="Also re-run approved tests on the same page (§16.3)")


# ---------- Test editing, dashboard ----------


class RegenerateIn(BaseModel):
    instructions: str = Field("", max_length=2000, description="What the reviewer wants changed")


class TestCaseVersionOut(ORM):
    __test__ = False
    version: int
    definition_json: dict
    source: str
    created_by: str
    created_at: datetime


# ---------- API inventory (Phase 7) ----------


class OpenApiImportIn(BaseModel):
    url: str | None = Field(None, description="Spec URL; must be inside the environment's scope")
    spec: dict | None = Field(None, description="Spec JSON pasted/uploaded directly")


class EndpointOut(ORM):
    id: uuid.UUID
    method: str
    path: str
    operation_id: str
    summary: str
    parameters_json: list
    has_request_body: bool
    response_content_type: str
    source: str
    last_seen_at: datetime


class GenerateApiTestsIn(BaseModel):
    scan_run_id: uuid.UUID
