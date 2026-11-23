"""Deterministic test validator (§9.6, §20.3). An LLM-generated test never runs unless this passes."""
import hashlib
import json

from app.schemas import Action, ScanPolicy, TestCaseDef
from app.scope import DESTRUCTIVE_RE, ScopeError, check_url

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "navigate": ("url",),
    "click": ("target",),
    "fill": ("target", "value"),
    "select": ("target", "value"),
    "check": ("target",),
    "uncheck": ("target",),
    "press": ("key",),
    "hover": ("target",),
    "wait_for": ("target",),
    "screenshot": (),
    "assert_text": ("text",),
    "assert_visible": ("target",),
    "assert_hidden": ("target",),
    "assert_url": ("value",),
    "assert_title": ("value",),
    "assert_value": ("target", "value"),
    "assert_count": ("target", "count"),
}
MAX_STEPS = 40


def _target_text(a: Action) -> str:
    t = a.target
    return " ".join(filter(None, [t.name, t.label, t.text, t.test_id, t.css])) if t else ""


def validate(test: TestCaseDef, base_url: str, policy: ScanPolicy) -> list[str]:
    errors: list[str] = []
    if not test.steps:
        errors.append("test has no steps")
    if len(test.steps) > MAX_STEPS:
        errors.append(f"test has more than {MAX_STEPS} steps")
    if not any(s.type.startswith("assert_") for s in test.steps):
        errors.append("test has no assertions (every test needs an observable assertion)")
    if test.steps and test.steps[0].type != "navigate":
        errors.append("first step must be navigate")
    try:
        check_url(test.target_url, base_url, policy, resolve=False)
    except ScopeError as e:
        errors.append(f"target_url out of scope: {e}")

    for i, s in enumerate(test.steps, 1):
        missing = [f for f in REQUIRED_FIELDS[s.type] if getattr(s, f) in (None, "")]
        if missing:
            errors.append(f"step {i} ({s.type}) missing {', '.join(missing)}")
        if s.target and not any(s.target.model_dump().values()):
            errors.append(f"step {i} target has no locator")
        if s.type == "navigate" and s.url:
            try:
                check_url(s.url, base_url, policy, resolve=False)
            except ScopeError as e:
                errors.append(f"step {i} navigates out of scope: {e}")
        if s.type in ("click", "press") and DESTRUCTIVE_RE.search(_target_text(s)) and not policy.destructive_actions_allowed:
            errors.append(f"step {i} clicks a potentially destructive control ({_target_text(s)!r})")
    if test.side_effect == "destructive" and not policy.destructive_actions_allowed:
        errors.append("test is classified destructive and the scan policy forbids destructive actions")
    return errors


def fingerprint(test: TestCaseDef) -> str:
    """Duplicate detection: identical step sequences are the same test regardless of wording."""
    steps = [s.model_dump(exclude={"description"}, exclude_none=True) for s in test.steps]
    return hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()
