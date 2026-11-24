"""Milestones D–F: failure → finding with evidence → assigned ticket → fix → automated retest → verified."""
from types import SimpleNamespace

import pytest

from app import findings as fx

API = "/api/v1"


def _setup(client, demo_url):
    p = client.post(f"{API}/projects", json={"name": "D-F flow"}).json()
    env = client.post(f"{API}/projects/{p['id']}/environments", json={
        "name": "local", "base_url": demo_url, "authorization_confirmed": True,
        "scan_policy": {"allow_private_network": True, "max_pages": 10, "max_depth": 1}}).json()
    scan = client.post(f"{API}/projects/{p['id']}/discovery", json={"environment_id": env["id"]}).json()
    client.post(f"{API}/projects/{p['id']}/tests/generate", json={"scan_run_id": scan["id"]})
    tests = client.get(f"{API}/projects/{p['id']}/test-cases").json()
    d1 = next(t for t in tests if t["title"] == "Add user: empty required fields are rejected")
    home = next(t for t in tests if t["title"].startswith("Welcome"))
    for t in (d1, home):
        client.post(f"{API}/test-cases/{t['id']}/approve")
    return p, env, d1, home


def _run(client, env, *tests):
    run = client.post(f"{API}/test-runs", json={"environment_id": env["id"], "test_case_ids": [t["id"] for t in tests]})
    return client.get(f"{API}/test-runs/{run.json()['id']}").json()


def test_finding_ticket_retest(client, demo):
    p, env, d1, home = _setup(client, demo.url)
    demo.module.FIXED = False

    # Milestone D — a failure becomes one evidence-backed finding; passing tests create none
    _run(client, env, d1, home)
    fs = client.get(f"{API}/projects/{p['id']}/findings").json()
    assert len(fs) == 1
    f = client.get(f"{API}/findings/{fs[0]['id']}").json()
    assert (f["status"], f["severity"], f["confidence"], f["occurrences"]) == ("new", "high", "probable", 1)
    assert f["reproduction_steps_json"][0].startswith("Open ") and "Create user" in f["reproduction_steps_json"][1]
    assert "/users?created=1" in f["actual_result"]
    assert f["original_screenshot_id"] and f["ai_analysis_json"]["is_hypothesis"] is True
    assert [e["event_type"] for e in f["events"]] == ["detected"]

    # Same failure again → same finding, now confirmed (reproduced), not a duplicate row
    _run(client, env, d1)
    f = client.get(f"{API}/findings/{f['id']}").json()
    assert len(client.get(f"{API}/projects/{p['id']}/findings").json()) == 1
    assert (f["occurrences"], f["confidence"]) == (2, "confirmed")

    # Human can't declare it verified; severity override needs a reason
    assert client.patch(f"{API}/findings/{f['id']}", json={"status": "verified"}).status_code == 409
    assert client.patch(f"{API}/findings/{f['id']}", json={"severity": "critical"}).status_code == 409
    r = client.patch(f"{API}/findings/{f['id']}", json={"severity": "medium", "reason": "only affects admins"})
    assert r.json()["severity"] == "medium"

    # Milestone E — finding → ticket assigned to a configured developer
    dev = client.post(f"{API}/projects/{p['id']}/developers", json={"name": "Dana Dev", "email": "dana@acme.test"}).json()
    t = client.post(f"{API}/findings/{f['id']}/ticket", json={"assignee_id": dev["id"]}).json()
    assert (t["number"], t["status"], t["assignee"]["name"], t["severity"]) == (1, "assigned", "Dana Dev", "medium")
    assert "### Steps to reproduce" in t["description"] and "hypothesis" in t["description"]
    assert client.post(f"{API}/findings/{f['id']}/ticket", json={}).status_code == 409  # no duplicate tickets
    client.post(f"{API}/findings/{f['id']}/comments", json={"body": "Looking into it"})
    client.patch(f"{API}/findings/{f['id']}", json={"status": "fixed", "reason": "added server-side check"})

    # Milestone F — retest while the bug is still there → reopened, not verified
    rr = client.post(f"{API}/findings/{f['id']}/retest", json={}).json()
    assert rr["retest_finding_id"] == f["id"]
    f = client.get(f"{API}/findings/{f['id']}").json()
    assert f["status"] == "reopened" and f["occurrences"] == 3

    # Developer ships the fix → retest replays the original test → verified, evidence kept
    demo.module.FIXED = True
    try:
        client.post(f"{API}/findings/{f['id']}/retest", json={"include_related": True})
    finally:
        demo.module.FIXED = False
    f = client.get(f"{API}/findings/{f['id']}").json()
    assert f["status"] == "verified"
    assert len(f["retest_runs"]) == 2 and f["retest_runs"][0]["executions"][0]["status"] == "passed"
    assert f["original_screenshot_id"]  # original failure evidence preserved
    kinds = [e["event_type"] for e in f["events"]]
    assert {"detected", "redetected", "severity", "ticket", "assigned", "comment", "retest"} <= set(kinds)
    assert client.get(f"{API}/projects/{p['id']}/tickets").json()[0]["status"] == "verified"
    assert client.post(f"{API}/findings/{f['id']}/retest", json={}).status_code == 409


def _db():
    return SimpleNamespace(add=lambda _: None, info={})


def test_secret_values_are_redacted():
    a = {"type": "fill", "target": {"label": "Password"}, "value": "hunter2"}
    assert "hunter2" not in fx.describe(fx.redact_action(a))
    b = {"type": "fill", "target": {"label": "Name"}, "value": "Alice"}
    assert fx.redact_action(b) == b


def test_only_retest_verifies_and_severity_needs_reason():
    f = SimpleNamespace(id=1, status="fixed", severity="high")
    with pytest.raises(fx.FindingError, match="retest"):
        fx.set_status(_db(), f, "verified")
    with pytest.raises(fx.FindingError, match="reason"):
        fx.set_severity(_db(), f, "low", " ")
    fx.set_status(_db(), f, "wont_fix")
    assert f.status == "wont_fix"
