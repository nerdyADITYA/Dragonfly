"""Milestones A–C end to end against the demo app: discover → generate → approve → execute → evidence."""


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_scan_requires_authorization(client, demo_url):
    p = client.post("/api/v1/projects", json={"name": "unauthorized"}).json()
    env = client.post(f"/api/v1/projects/{p['id']}/environments", json={
        "name": "local", "base_url": demo_url, "scan_policy": {"allow_private_network": True}}).json()
    r = client.post(f"/api/v1/projects/{p['id']}/discovery", json={"environment_id": env["id"]})
    assert r.status_code == 409


def test_private_target_rejected_without_opt_in(client, demo_url):
    p = client.post("/api/v1/projects", json={"name": "ssrf"}).json()
    r = client.post(f"/api/v1/projects/{p['id']}/environments", json={
        "name": "local", "base_url": demo_url, "authorization_confirmed": True})
    assert r.status_code == 422


def test_vertical_slice(client, demo_url):
    api = "/api/v1"
    p = client.post(f"{api}/projects", json={"name": "Acme Tasks", "description": "demo"}).json()
    env = client.post(f"{api}/projects/{p['id']}/environments", json={
        "name": "local", "base_url": demo_url, "environment_type": "local", "authorization_confirmed": True,
        "scan_policy": {"allow_private_network": True, "max_pages": 15, "max_depth": 2}}).json()

    # Milestone A — discovery (eager Celery: runs inline)
    scan = client.post(f"{api}/projects/{p['id']}/discovery", json={"environment_id": env["id"]}).json()
    scan = client.get(f"{api}/discovery/{scan['id']}").json()
    assert scan["status"] == "completed", scan
    pages = client.get(f"{api}/discovery/{scan['id']}/pages").json()
    urls = {pg["url"] for pg in pages}
    assert {demo_url.rstrip("/") + x for x in ("/login", "/users", "/users/new", "/search")} <= urls
    assert not any("/delete" in u for u in urls), "explorer followed a destructive link"
    assert not any("example.com" in u for u in urls), "explorer left scope"
    s = scan["summary_json"]
    assert s["skipped_destructive"] >= 1 and s["skipped_out_of_scope"] >= 1
    assert any(f["name"] == "Add user" for pg in pages for f in pg["forms"])
    assert all(pg["screenshot_artifact_id"] for pg in pages)

    # Milestone B — generation (rule-based: no API key in tests)
    gen = client.post(f"{api}/projects/{p['id']}/tests/generate", json={"scan_run_id": scan["id"]}).json()
    assert gen["created"] > 0 and gen["generated_by"] == "rules"
    again = client.post(f"{api}/projects/{p['id']}/tests/generate", json={"scan_run_id": scan["id"]}).json()
    assert again["created"] == 0 and again["duplicates_skipped"] == gen["candidates"]
    tests = client.get(f"{api}/projects/{p['id']}/test-cases").json()
    assert all(t["status"] == "draft" for t in tests)

    # Unapproved tests cannot run
    ids = [t["id"] for t in tests]
    assert client.post(f"{api}/test-runs", json={"environment_id": env["id"], "test_case_ids": ids}).status_code == 409
    for t in tests:
        assert client.post(f"{api}/test-cases/{t['id']}/approve").json()["status"] == "approved"

    # Milestone C — execution with deterministic verdicts and evidence
    run = client.post(f"{api}/test-runs", json={"environment_id": env["id"], "test_case_ids": ids}).json()
    run = client.get(f"{api}/test-runs/{run['id']}").json()
    assert run["status"] == "completed"
    by_key = {t["id"]: t for t in tests}
    results = {by_key[e["test_case_id"]]["title"]: e for e in run["executions"]}

    home = next(e for title, e in results.items() if title.startswith("Welcome"))
    assert home["status"] == "passed", home

    # Known defect D1: empty Name is accepted on /users/new
    d1 = results["Add user: empty required fields are rejected"]
    assert d1["status"] == "failed" and d1["failure_type"] == "assertion", d1
    detail = client.get(f"{api}/test-executions/{d1['id']}").json()
    failed_step = next(s for s in detail["steps"] if s["status"] == "failed")
    assert failed_step["screenshot_artifact_id"]
    assert {a["artifact_type"] for a in detail["artifacts"]} >= {"screenshot", "trace"}
    assert "/users" in next(a for a in detail["assertion_results_json"] if not a["passed"])["actual"]
    shot = client.get(f"{api}/artifacts/{failed_step['screenshot_artifact_id']}")
    assert shot.status_code == 200 and shot.content[:4] == b"\x89PNG"

    # Login form uses HTML5 required → browser blocks empty submit → passes
    assert results["Login: empty required fields are rejected"]["status"] == "passed"

    # Dashboard page error (D6) is captured as evidence
    dash = next(e for title, e in results.items() if title.startswith("Dashboard"))
    assert any("renderWidgets" in m for m in dash["execution_metadata_json"]["browser_events"]["page_errors"])

    # Rerun
    rr = client.post(f"{api}/test-executions/{d1['id']}/rerun").json()
    rr = client.get(f"{api}/test-runs/{rr['id']}").json()
    assert rr["executions"][0]["status"] == "failed"
