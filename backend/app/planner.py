"""AI Test Planner (§9, §20.2). Turns discovery output into schema-valid TestCaseDefs.

Providers: Claude (structured outputs) and a deterministic rule-based generator used when no API key is
configured or the AI call fails. Either way, every test goes through validator.validate before it can run.
"""
import json
import logging
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import ai
from app.models import DiscoveredPage, Environment, ScanRun, TestCase, TestCaseVersion
from app.schemas import Action, ScanPolicy, Target, TestCaseDef, TestPlan
from app.validator import fingerprint, validate

log = logging.getLogger(__name__)
PROMPT_VERSION = "planner-v1"

SYSTEM_PROMPT = """You are the test planner inside Dragonfly, an automated QA platform.
You receive a JSON summary of pages, interactive elements and forms that a crawler discovered on a web
application the user is authorized to test. Produce browser test cases that a deterministic Playwright
executor will run step by step.

Rules:
- Use only the action types in the schema. The first step must be `navigate` to an absolute in-scope URL.
- Every test needs at least one assert_* step that checks something observable (text, URL, title,
  visibility, input value, element count). Prefer assertions that would catch a real defect.
- Locate elements with `target`, preferring role+name, then label, then placeholder, test_id, text; use css
  only as a last resort. Use only names/labels that appear in the discovery data.
- Never click delete/purchase/send/transfer/publish/logout-style controls. Set side_effect to
  "writes_data" for tests that submit forms, "destructive" only if unavoidable (it will be blocked).
- Cover: page loads, navigation, form validation (required fields, invalid formats, boundary values),
  search behaviour (including case-insensitivity), pagination, and edge cases (long input, unicode, whitespace).
- Do not invent credentials. If a test needs a login, list it under data_requirements.
- Keys look like AREA-CATEGORY-NNN, e.g. USERS-VAL-001. Keep each test focused on one behaviour.
- source_observations must cite the page URL(s) or form names you based the test on."""


def discovery_summary(db: Session, scan: ScanRun) -> dict:
    pages = db.scalars(select(DiscoveredPage).where(DiscoveredPage.scan_run_id == scan.id)
                       .options(selectinload(DiscoveredPage.elements), selectinload(DiscoveredPage.forms))).all()
    return {"pages": [{
        "url": p.url, "title": p.title, "status_code": p.status_code,
        "elements": [{"role": e.element_type, "name": e.accessible_name, **e.attributes_json}
                     for e in p.elements if e.is_visible][:60],
        "forms": [{"name": f.name, "method": f.method, "action": f.action, "submit": f.submit_label,
                   "fields": f.fields_json} for f in p.forms],
    } for p in pages]}


# ---------------- rule-based provider ----------------

def _slug(url: str) -> str:
    seg = [s for s in urlsplit(url).path.split("/") if s]
    return (seg[0] if seg else "home").upper().replace("-", "")[:12]


def rule_based_plan(summary: dict) -> list[TestCaseDef]:
    tests: list[TestCaseDef] = []
    n = 0
    for p in summary["pages"]:
        area, path = _slug(p["url"]), urlsplit(p["url"]).path or "/"
        n += 1
        steps = [Action(type="navigate", url=p["url"], description=f"Open {path}"),
                 Action(type="assert_url", value=path, description="URL is the requested page")]
        if p["title"]:
            steps.append(Action(type="assert_title", value=p["title"], description="Page title matches discovery"))
        heading = next((e["name"] for e in p["elements"] if e["role"] == "heading"), None)
        if heading:
            steps.append(Action(type="assert_visible", target=Target(role="heading", name=heading)))
        tests.append(TestCaseDef(
            key=f"{area}-FUNC-{n:03d}", title=f"{p['title'] or path} page loads", category="functional",
            priority="P1", risk="low", target_url=p["url"], steps=steps,
            expected_outcomes=["Page loads without redirecting away", "Title matches the discovered title"],
            confidence=0.9, source_observations=[f"page {p['url']}"]))

        for f in p["forms"]:
            if f["method"] != "post" or not f["submit"]:
                continue
            submit = Target(role="button", name=f["submit"])
            req_like = [fl for fl in f["fields"] if fl["required"] or "*" in (fl["label"] or "")]
            if req_like:
                n += 1
                tests.append(TestCaseDef(
                    key=f"{area}-VAL-{n:03d}", title=f"{f['name']}: empty required fields are rejected",
                    description="Submitting the form with all fields empty must not succeed.",
                    category="validation", priority="P1", risk="medium", target_url=p["url"],
                    steps=[Action(type="navigate", url=p["url"]),
                           Action(type="click", target=submit, description="Submit the empty form"),
                           Action(type="assert_url", value=path, description="Still on the form page (submission rejected)")],
                    expected_outcomes=["The form is not accepted", "User stays on the form with a validation message"],
                    side_effect="writes_data", confidence=0.75,
                    source_observations=[f"form '{f['name']}' on {p['url']}; required-looking fields: "
                                         + ", ".join(fl["label"] or fl["name"] for fl in req_like)]))
    return tests


# ---------------- Claude provider ----------------

def claude_plan(summary: dict, policy: ScanPolicy, base_url: str, goals: str) -> list[TestCaseDef]:
    user = (f"Base URL: {base_url}\nAllowed domains: {policy.allowed_domains or [urlsplit(base_url).hostname]}\n"
            f"Destructive actions allowed: {policy.destructive_actions_allowed}\n"
            f"User testing goals: {goals or '(none given — use your judgement)'}\n\n"
            f"Discovery data:\n{json.dumps(summary, ensure_ascii=False)}\n\n"
            "Generate 8–20 high-value test cases.")
    return ai.structured(SYSTEM_PROMPT, user, TestPlan).tests


# ---------------- orchestration ----------------

def generate_tests(db: Session, scan: ScanRun, goals: str = "", use_ai: bool = True) -> dict:
    env = db.get(Environment, scan.environment_id)
    policy = ScanPolicy(**scan.scan_policy_snapshot)
    summary = discovery_summary(db, scan)
    if not summary["pages"]:
        raise ValueError("scan discovered no pages")

    source, note = "rules", None
    candidates: list[TestCaseDef] = []
    if use_ai and ai.enabled():
        try:
            candidates = claude_plan(summary, policy, env.base_url, goals)
            source = ai.model_tag(PROMPT_VERSION)
        except Exception as e:  # AI failure must never block the workflow (§62)
            log.exception("AI planner failed; using rule-based planner")
            note = f"AI planner failed ({type(e).__name__}: {str(e)[:200]}); used rule-based planner"
    elif use_ai:
        note = "ANTHROPIC_API_KEY not set; used rule-based planner"
    if not candidates:
        candidates = rule_based_plan(summary)

    existing = set(db.scalars(select(TestCase.fingerprint).where(TestCase.project_id == scan.project_id)))
    created = duplicates = blocked = 0
    for t in candidates:
        fp = fingerprint(t)
        if fp in existing:
            duplicates += 1
            continue
        existing.add(fp)
        tc = TestCase(project_id=scan.project_id, scan_run_id=scan.id, generated_by=source, version=0)
        db.add(tc)
        set_definition(db, tc, t, env.base_url, policy, f"generated:{source}")
        blocked += tc.status == "blocked"
        created += 1
    db.commit()
    return {"generated_by": source, "candidates": len(candidates), "created": created,
            "duplicates_skipped": duplicates, "blocked_by_validator": blocked, "note": note}


# ---------------- versioning, regeneration ----------------

def set_definition(db: Session, tc: TestCase, d: TestCaseDef, base_url: str, policy: ScanPolicy, source: str,
                   actor: str = "system") -> None:
    """The only way a test definition changes: validate, bump version, record history, back to review."""
    errors = validate(d, base_url, policy)
    tc.definition_json, tc.key, tc.title = d.model_dump(), d.key[:60], d.title[:300]
    tc.category, tc.priority, tc.fingerprint = d.category, d.priority, fingerprint(d)
    tc.version = (tc.version or 0) + 1
    tc.validation_errors_json, tc.status = errors, "blocked" if errors else "draft"
    db.flush()
    db.add(TestCaseVersion(test_case_id=tc.id, version=tc.version, definition_json=tc.definition_json,
                           source=source[:80], created_by=actor))


REGEN_PROMPT = SYSTEM_PROMPT + """

You are rewriting ONE existing test case. Keep its intent unless the reviewer's instructions say otherwise,
fix whatever the reviewer or the validation errors point out, and keep the same key."""


def regenerate_test(db: Session, tc: TestCase, instructions: str) -> None:
    if not ai.enabled():
        raise ValueError("Regenerating a test needs the AI planner (set ANTHROPIC_API_KEY)")
    scan = db.get(ScanRun, tc.scan_run_id) if tc.scan_run_id else None
    if not scan:
        raise ValueError("test has no source scan to regenerate from")
    env = db.get(Environment, scan.environment_id)
    user = (f"Discovery data:\n{json.dumps(discovery_summary(db, scan), ensure_ascii=False)}\n\n"
            f"Current test:\n{json.dumps(tc.definition_json, ensure_ascii=False)}\n\n"
            f"Validation errors: {tc.validation_errors_json or 'none'}\n"
            f"Reviewer instructions: {instructions or '(none — improve clarity and assertions)'}")
    d = ai.structured(REGEN_PROMPT, user, TestCaseDef)
    set_definition(db, tc, d, env.base_url, ScanPolicy(**env.scan_policy), f"regenerated:{ai.model_tag(PROMPT_VERSION)}",
                   actor="user")
