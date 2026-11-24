"""API inventory (§11) and rule-based API + security test generation (§12).

Endpoints come from an OpenAPI spec or from XHR/fetch calls seen during discovery.
Generated tests are ordinary TestCases (category api/security) that go through the same
validator, human approval, executor, findings and retest pipeline as browser tests.
"""
import json
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.http_checks import LEAK_PATTERN, SECRET_KEY_PATTERN, USER_AGENT
from app.models import DiscoveredEndpoint, DiscoveredForm, DiscoveredPage, Environment, ScanRun, TestCase
from app.planner import set_definition
from app.schemas import Action, ScanPolicy, TestCaseDef
from app.scope import DESTRUCTIVE_RE, check_url
from app.target_auth import profile_for
from app.validator import fingerprint

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
MAX_SPEC_BYTES = 5_000_000
GENERATOR = "rules:api-security-v1"
CORS_PROBE_ORIGIN = "https://dragonfly-cors-probe.invalid"


# ---------------- inventory ----------------

def fetch_spec(env: Environment, url: str) -> dict:
    """Fetch a spec through the same scope/SSRF guard as scans."""
    policy = ScanPolicy(**env.scan_policy)
    check_url(url, env.base_url, policy)
    with httpx.Client(timeout=15, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as c:
        r = c.get(url)
    if r.status_code != 200:
        raise ValueError(f"spec URL returned HTTP {r.status_code}")
    if len(r.content) > MAX_SPEC_BYTES:
        raise ValueError("spec is larger than 5 MB")
    try:
        return r.json()
    except ValueError as e:
        raise ValueError("spec is not JSON (YAML specs are not supported yet)") from e


def _upsert(db: Session, env: Environment, method: str, path: str, source: str, **fields) -> bool:
    ep = db.scalars(select(DiscoveredEndpoint).where(DiscoveredEndpoint.environment_id == env.id,
                                                     DiscoveredEndpoint.method == method,
                                                     DiscoveredEndpoint.path == path)).first()
    created = ep is None
    if created:
        ep = DiscoveredEndpoint(project_id=env.project_id, environment_id=env.id, method=method, path=path,
                                source=source)
        db.add(ep)
    elif source == "openapi":
        ep.source = "openapi"  # the spec is the richer description; network sightings keep last_seen fresh
    for k, v in fields.items():
        setattr(ep, k, v)
    ep.last_seen_at = datetime.now(UTC)
    return created


def import_openapi(db: Session, env: Environment, spec: dict) -> dict:
    if not isinstance(spec.get("paths"), dict):
        raise ValueError("not an OpenAPI document (no `paths`)")  # noqa: TRY004  (user input, surfaced as HTTP 422)
    components = spec.get("components") or {}
    created = updated = 0
    for path, item in spec["paths"].items():
        if not isinstance(item, dict):
            continue
        for method in HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            params = [{"name": p.get("name"), "in": p.get("in"), "required": bool(p.get("required")),
                       "type": (p.get("schema") or {}).get("type", "string")}
                      for p in [*item.get("parameters", []), *op.get("parameters", [])] if isinstance(p, dict)]
            ok = next((v for k, v in (op.get("responses") or {}).items() if str(k).startswith("2")), {}) or {}
            ctype, media = next(iter((ok.get("content") or {}).items()), ("", {}))
            schema = (media or {}).get("schema") or None
            if schema and components:
                schema = {**schema, "components": components}  # lets "#/components/..." $refs resolve
            new = _upsert(db, env, method.upper(), path[:1000], "openapi", operation_id=str(op.get("operationId", ""))[:200],
                          summary=str(op.get("summary", ""))[:500], parameters_json=params,
                          has_request_body="requestBody" in op, response_content_type=ctype[:100],
                          response_schema_json=schema,
                          requires_auth=bool(op.get("security", spec.get("security"))))
            created += new
            updated += not new
    db.commit()
    return {"created": created, "updated": updated}


def record_network_calls(db: Session, env: Environment, calls: set[tuple[str, str]]) -> int:
    """XHR/fetch requests observed while exploring (§11.1 'browser network activity')."""
    n = 0
    for method, url in calls:
        n += _upsert(db, env, method, urlsplit(url).path or "/", "network")
    return n


# ---------------- generation ----------------

def _t(key, title, category, priority, url, steps, *, side_effect="none", description="", sources=(), outcomes=()):
    return TestCaseDef(key=key, title=title, category=category, priority=priority, risk="medium", target_url=url,
                       steps=steps, side_effect=side_effect, description=description, confidence=0.9,
                       expected_outcomes=list(outcomes), source_observations=list(sources))


def _get(url, headers=None, desc=""):
    return Action(type="api_request", method="GET", url=url, headers=json.dumps(headers) if headers else None,
                  description=desc or f"GET {urlsplit(url).path}")


def _sample(param_type: str, kind: str) -> str:
    """Path value for a probe: a non-existent id, or a value of the wrong type."""
    if kind == "missing":
        return "999999999" if param_type in ("integer", "number") else "dragonfly-nonexistent-id"
    return "not-a-number" if param_type in ("integer", "number") else ""


def api_tests(endpoints: list[DiscoveredEndpoint], base: str, authenticated: bool = False
              ) -> tuple[list[TestCaseDef], list[dict]]:
    tests, skipped = [], []
    for n, ep in enumerate(sorted(endpoints, key=lambda e: (e.path, e.method)), 1):
        label = f"{ep.method} {ep.path}"
        words = f"{ep.path} {ep.summary} {ep.operation_id}".replace("/", " ").replace("_", " ").replace("-", " ")
        if ep.method != "GET":
            skipped.append({"endpoint": label, "reason": "state-changing method; generated only for GET"})
            continue
        if DESTRUCTIVE_RE.search(words):
            skipped.append({"endpoint": label, "reason": "looks destructive"})
            continue
        if ep.requires_auth and not authenticated:
            skipped.append({"endpoint": label, "reason": "requires sign-in: add a login profile to test it"})
            continue
        path_params = [p for p in ep.parameters_json if p["in"] == "path"]
        if any(p["in"] == "query" and p["required"] for p in ep.parameters_json):
            skipped.append({"endpoint": label, "reason": "needs required query parameters"})
            continue
        json_api = ep.response_content_type.startswith("application/json") or ep.source == "network"
        src = [f"{ep.source}: {label}"]
        if not json_api:
            skipped.append({"endpoint": label, "reason": "HTML page (covered by browser tests)"})
            continue
        if not path_params:
            url = urljoin(base, ep.path.lstrip("/"))
            steps = [_get(url), Action(type="assert_status", value="2xx", description="Responds successfully")]
            schema = {k: v for k, v in (ep.response_schema_json or {}).items() if k != "components"}
            if schema:
                steps.append(Action(type="assert_json_schema", json_schema=json.dumps(ep.response_schema_json),
                                    description="Body matches the documented response schema"))
            tests.append(_t(f"API-{n:03d}", f"{label} responds with 2xx" + (" and documented schema" if len(steps) > 2 else ""),
                            "api", "P2", url, steps, sources=src, outcomes=["2xx status", "valid response body"]))
            tests.append(_t(f"SEC-DATA-{n:03d}", f"{label} does not expose secret fields", "security", "P1", url,
                            [_get(url), Action(type="assert_body_not", value=SECRET_KEY_PATTERN,
                                               description="No password/token/secret keys in the response")],
                            sources=src, outcomes=["No credential-like fields are returned"]))
            continue
        for kind, want, title in (("missing", "404", "returns 404 for a non-existent id"),
                                  ("invalid", "4xx", "rejects a malformed id with 4xx")):
            if kind == "invalid" and not any(p["type"] in ("integer", "number") for p in path_params):
                continue
            path = ep.path
            for p in path_params:
                path = path.replace("{" + p["name"] + "}", _sample(p["type"], kind) or "x")
            url = urljoin(base, path.lstrip("/"))
            tests.append(_t(f"API-{n:03d}-{kind.upper()}", f"{label} {title}", "api", "P2", url,
                            [_get(url), Action(type="assert_status", value=want, description=f"Expect HTTP {want}")],
                            sources=src, outcomes=[f"HTTP {want}"]))
    return tests, skipped


SECURITY_HEADERS = [  # (header, regex or None, priority, why)
    ("Content-Security-Policy", None, "P2", "limits script sources and mitigates XSS"),
    ("X-Content-Type-Options", "nosniff", "P3", "stops MIME-type sniffing"),
    ("X-Frame-Options", "deny|sameorigin", "P3", "prevents clickjacking via framing"),
    ("Referrer-Policy", None, "P3", "limits URL leakage to other sites"),
]


def security_tests(db: Session, scan: ScanRun, env: Environment, endpoints: list[DiscoveredEndpoint],
                   policy: ScanPolicy, authenticated: bool = False) -> list[TestCaseDef]:
    base = env.base_url
    https = urlsplit(base).scheme == "https"
    src = [f"base URL {base}"]
    out = [_t(f"SEC-HDR-{i:02d}", f"{h} header is set", "security", prio, base,
              [_get(base), Action(type="assert_header", key=h, value=rx, description=f"{h} {why}")],
              sources=src, description=f"Passive check: the {h} response header {why}.",
              outcomes=[f"{h} present" + (f" and matching {rx}" if rx else "")])
           for i, (h, rx, prio, why) in enumerate(SECURITY_HEADERS + ([("Strict-Transport-Security", "max-age=[1-9]", "P2",
                                                                        "forces HTTPS on later visits")] if https else []), 1)]
    out.append(_t("SEC-COOKIE-01", "Cookies set on the home page carry security flags", "security", "P2", base,
                  [_get(base), Action(type="assert_cookies_secure", description="HttpOnly + SameSite (+ Secure on HTTPS)")],
                  sources=src))
    probe = urljoin(base, "dragonfly-probe-not-found-7f3a")
    out.append(_t("SEC-ERR-01", "Error pages do not expose internals", "security", "P2", probe,
                  [_get(probe, desc="Request a page that does not exist"),
                   Action(type="assert_body_not", value=LEAK_PATTERN, description="No stack traces, file paths or SQL")],
                  sources=src, outcomes=["Generic error message without implementation details"]))
    cors_target = next((urljoin(base, e.path.lstrip("/")) for e in sorted(endpoints, key=lambda e: e.path)
                        if e.method == "GET" and "{" not in e.path and (authenticated or not e.requires_auth)
                        and e.response_content_type.startswith("application/json")), base)
    out.append(_t("SEC-CORS-01", "CORS does not trust arbitrary origins", "security", "P1", cors_target,
                  [_get(cors_target, {"Origin": CORS_PROBE_ORIGIN}, "GET with a foreign Origin header"),
                   Action(type="assert_header_not", key="Access-Control-Allow-Origin",
                          value=CORS_PROBE_ORIGIN.replace(".", r"\."), description="Foreign origin is not reflected")],
                  sources=[f"endpoint {cors_target}"]))

    if policy.security_profile == "standard":  # low-volume active probes (§12.3)
        forms = db.scalars(select(DiscoveredForm).join(DiscoveredPage)
                           .where(DiscoveredPage.scan_run_id == scan.id, DiscoveredForm.method == "post")).all()
        for i, f in enumerate([f for f in forms if any(x["type"] == "password" for x in f.fields_json)], 1):
            body = {x["name"]: ("dragonfly-probe@invalid.test" if x["type"] == "email" or "mail" in x["name"].lower()
                                else "dragonfly-probe-wrong-password" if x["type"] == "password" else "dragonfly")
                    for x in f.fields_json}
            out.append(_t(f"SEC-AUTH-{i:02d}", f"Failed sign-in on “{f.name}” does not reveal internals", "security",
                          "P2", f.action, side_effect="writes_data",
                          steps=[Action(type="api_request", method="POST", url=f.action, body=json.dumps(body),
                                        value="form", description="Submit an invalid, non-existent account"),
                                 Action(type="assert_body_not", value=LEAK_PATTERN,
                                        description="Error is generic: no stack traces, file paths or SQL")],
                          description="Standard-profile probe: one failed login with a fake account (§12.2).",
                          sources=[f"form '{f.name}' posting to {f.action}"],
                          outcomes=["A generic 'invalid credentials' message"]))
    return out


def generate(db: Session, scan: ScanRun) -> dict:
    env = db.get(Environment, scan.environment_id)
    policy = ScanPolicy(**env.scan_policy)
    endpoints = db.scalars(select(DiscoveredEndpoint).where(DiscoveredEndpoint.environment_id == env.id)).all()
    authenticated = profile_for(db, env) is not None  # tests then run with the signed-in session
    candidates, skipped = api_tests(endpoints, env.base_url, authenticated)
    if policy.security_profile != "off":
        candidates += security_tests(db, scan, env, endpoints, policy, authenticated)
    existing = set(db.scalars(select(TestCase.fingerprint).where(TestCase.project_id == scan.project_id)))
    created = blocked = dup = 0
    by_category = {"api": 0, "security": 0}
    for t in candidates:
        if (fp := fingerprint(t)) in existing:
            dup += 1
            continue
        existing.add(fp)
        tc = TestCase(project_id=scan.project_id, scan_run_id=scan.id, generated_by=GENERATOR, version=0)
        db.add(tc)
        set_definition(db, tc, t, env.base_url, policy, f"generated:{GENERATOR}")
        blocked += tc.status == "blocked"
        by_category[t.category] += 1
        created += 1
    db.commit()
    return {"generated_by": GENERATOR, "endpoints": len(endpoints), "authenticated": authenticated,
            "created": created, "by_category": by_category,
            "duplicates_skipped": dup, "blocked_by_validator": blocked, "skipped_endpoints": skipped,
            "security_profile": policy.security_profile}
