"""Phases 7–8: OpenAPI inventory → API + security tests → findings for demo defects D5–D8."""
import json

import httpx
import pytest

from app.http_checks import evidence
from app.schemas import Action, ScanPolicy, TestCaseDef
from app.validator import validate

API = "/api/v1"


def _project(client, demo_url, **policy):
    p = client.post(f"{API}/projects", json={"name": "API + security"}).json()
    env = client.post(f"{API}/projects/{p['id']}/environments", json={
        "name": "local", "base_url": demo_url, "authorization_confirmed": True,
        "scan_policy": {"allow_private_network": True, "max_pages": 10, "max_depth": 1,
                        "requests_per_second": 50, **policy}}).json()
    scan = client.post(f"{API}/projects/{p['id']}/discovery", json={"environment_id": env["id"]}).json()
    return p, env, scan


def _run(client, env, ids):
    run = client.post(f"{API}/test-runs", json={"environment_id": env["id"], "test_case_ids": ids}).json()
    return client.get(f"{API}/test-runs/{run['id']}").json()


def test_api_and_security_detect_demo_defects(client, demo):
    demo.module.FIXED = False
    p, env, scan = _project(client, demo.url, security_profile="standard")

    # Inventory from the demo app's own OpenAPI spec, fetched through the scope guard
    imp = client.post(f"{API}/environments/{env['id']}/openapi", json={"url": demo.url + "openapi.json"}).json()
    assert imp["created"] >= 5
    eps = {f"{e['method']} {e['path']}" for e in client.get(f"{API}/environments/{env['id']}/endpoints").json()}
    assert {"GET /api/users", "GET /api/users/{user_id}", "POST /login"} <= eps
    again = client.post(f"{API}/environments/{env['id']}/openapi", json={"url": demo.url + "openapi.json"}).json()
    assert again["created"] == 0  # deduplicated

    gen = client.post(f"{API}/projects/{p['id']}/tests/generate-api", json={"scan_run_id": scan["id"]}).json()
    assert gen["blocked_by_validator"] == 0 and gen["by_category"]["security"] >= 7
    assert any("delete" in s["endpoint"] and s["reason"] == "looks destructive" for s in gen["skipped_endpoints"])
    tests = [t for t in client.get(f"{API}/projects/{p['id']}/test-cases").json() if t["category"] in ("api", "security")]
    for t in tests:
        client.post(f"{API}/test-cases/{t['id']}/approve")
    run = _run(client, env, [t["id"] for t in tests])
    title = {t["id"]: t["title"] for t in tests}
    res = {title[e["test_case_id"]]: e for e in run["executions"]}

    assert res["GET /api/users/{user_id} returns 404 for a non-existent id"]["status"] == "failed"     # D5
    assert res["GET /api/users/{user_id} rejects a malformed id with 4xx"]["status"] == "passed"
    for h in ("Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"):  # D8
        assert res[f"{h} header is set"]["status"] == "failed", h
    login = next(e for t, e in res.items() if t.startswith("Failed sign-in"))
    assert login["status"] == "failed"                                                                 # D7
    for ok in ("Error pages do not expose internals", "CORS does not trust arbitrary origins",
               "GET /api/users does not expose secret fields", "Cookies set on the home page carry security flags"):
        assert res[ok]["status"] == "passed", ok

    # Findings carry sanitized HTTP evidence instead of screenshots
    fs = client.get(f"{API}/projects/{p['id']}/findings").json()
    assert len(fs) == 6 and sum(f["category"] == "security" for f in fs) == 5
    d5 = next(f for f in fs if "404" in f["title"])
    ev = client.get(f"{API}/findings/{d5['id']}").json()["http_evidence"]
    assert ev["response"]["status"] == 200 and ev["request"]["method"] == "GET"
    d7 = client.get(f"{API}/findings/{next(f['id'] for f in fs if 'sign-in' in f['title'])}").json()
    assert "users_table" in d7["http_evidence"]["response"]["body_excerpt"]
    assert "wrong-password" not in json.dumps(d7["reproduction_steps_json"])
    dash = client.get(f"{API}/dashboard", params={"project_id": p["id"]}).json()
    assert dash["findings"]["open_by_category"] == {"api": 1, "security": 5}
    html = client.get(f"{API}/scan-runs/{scan['id']}/report").text
    assert "Security checks (" in html and "HTTP evidence" in html

    # The fix for D5 verifies through the normal retest flow
    demo.module.FIXED = True
    try:
        client.post(f"{API}/findings/{d5['id']}/retest", json={})
    finally:
        demo.module.FIXED = False
    assert client.get(f"{API}/findings/{d5['id']}").json()["status"] == "verified"


def test_page_errors_fail_page_load_tests(client, demo):  # D6
    p, env, scan = _project(client, demo.url)
    client.post(f"{API}/projects/{p['id']}/tests/generate", json={"scan_run_id": scan["id"]})
    dash = next(t for t in client.get(f"{API}/projects/{p['id']}/test-cases").json() if t["title"].startswith("Dashboard"))
    client.post(f"{API}/test-cases/{dash['id']}/approve")
    ex = _run(client, env, [dash["id"]])["executions"][0]
    assert ex["status"] == "failed" and "renderWidgets" in ex["assertion_results_json"][-1]["actual"]


def test_passive_profile_skips_active_probes_and_budget_is_enforced(client, demo):
    p, env, scan = _project(client, demo.url, max_requests=1)
    client.post(f"{API}/environments/{env['id']}/openapi", json={"url": demo.url + "openapi.json"})
    gen = client.post(f"{API}/projects/{p['id']}/tests/generate-api", json={"scan_run_id": scan["id"]}).json()
    assert gen["security_profile"] == "passive"
    tests = client.get(f"{API}/projects/{p['id']}/test-cases").json()
    assert not any(t["title"].startswith("Failed sign-in") for t in tests)
    two = [t for t in tests if t["category"] == "security"][:2]
    for t in two:
        client.post(f"{API}/test-cases/{t['id']}/approve")
    statuses = sorted(e["status"] for e in _run(client, env, [t["id"] for t in two])["executions"])
    assert "blocked" in statuses  # second request exceeds max_requests=1


def test_spec_url_must_be_in_scope(client, demo):
    _, env, _ = _project(client, demo.url)
    r = client.post(f"{API}/environments/{env['id']}/openapi", json={"url": "https://example.com/openapi.json"})
    assert r.status_code == 422 and "scope" in r.json()["detail"]


# ---------------- unit: validator + evidence ----------------

BASE = "http://127.0.0.1:8001/"
POL = ScanPolicy(allow_private_network=True)


def _http(*steps, **kw):
    base = {"key": "T", "title": "t", "category": "api", "priority": "P2", "target_url": BASE}
    return TestCaseDef(steps=[Action(type="api_request", method="GET", url=BASE), *steps], **(base | kw))


@pytest.mark.parametrize("step,kw,needle", [
    (Action(type="api_request", method="DELETE", url=BASE + "api/users/1"), {}, "destructive"),
    (Action(type="api_request", method="GET", url=BASE + "users/1/delete"), {}, "destructive"),
    (Action(type="api_request", method="POST", url=BASE + "api/users"), {}, "writes_data"),
    (Action(type="api_request", method="GET", url=BASE, headers='{"Authorization": "Bearer x"}'), {}, "credentials"),
    (Action(type="click", target={"text": "x"}), {}, "other kind"),
    (Action(type="api_request", method="POST", url=BASE + "login", body="{}"),
     {"category": "security", "side_effect": "writes_data"}, "security_profile=standard"),
    (Action(type="assert_body_not", value="("), {}, "regex"),
])
def test_http_validator_rules(step, kw, needle):
    errs = validate(_http(step, Action(type="assert_status", value="200"), **kw), BASE, POL)
    assert any(needle in e for e in errs), errs


def test_security_off_blocks_security_tests():
    t = _http(Action(type="assert_header", key="X-Frame-Options"), category="security")
    assert any("security_profile=off" in e for e in validate(t, BASE, ScanPolicy(allow_private_network=True,
                                                                                    security_profile="off")))


def test_leak_excerpt_is_plain_text():
    from app.http_checks import LEAK_PATTERN, HttpSession

    s = HttpSession(BASE, POL, {"left": 1})
    page = '<nav><a href="/search">Search</a></nav>' + "x" * 60 + \
        '<p class="error">AuthError at auth.py:42 &mdash; no row WHERE email=&#x27;a@b.c&#x27;</p>' + "y" * 60
    s.resp = httpx.Response(200, text=page, request=httpx.Request("POST", BASE))
    with pytest.raises(AssertionError):
        s.assert_body_not(Action(type="assert_body_not", value=LEAK_PATTERN))
    assert "<" not in s.actual and ">" not in s.actual and "AuthError at auth.py:42 — no row WHERE email='a@b.c'" in s.actual
    s.close()


def test_evidence_is_sanitized():
    req = httpx.Request("POST", "http://x.test/api?token=abc", headers={"Authorization": "Bearer s3cr3t"})
    resp = httpx.Response(200, request=req, headers={"Set-Cookie": "session=abc123; HttpOnly"},
                          json={"user": "a", "password": "hunter2", "access_token": "t0k"})
    ev = json.dumps(evidence(resp, 5))
    for secret in ("s3cr3t", "abc123", "hunter2", "t0k", "token=abc"):
        assert secret not in ev, secret
