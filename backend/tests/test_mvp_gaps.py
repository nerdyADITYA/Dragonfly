"""Dashboard, scan report, app map, test versions/duplicate/regenerate, live events."""
from app import events
from tests.test_findings_flow import _run, _setup

API = "/api/v1"


def test_mvp_gaps(client, demo):
    demo.module.FIXED = False
    p, env, d1, home = _setup(client, demo.url)
    run = _run(client, env, d1, home)
    scan_id = client.get(f"{API}/projects/{p['id']}/scans").json()[0]["id"]

    # Dashboard numbers reconcile with the underlying rows (§51 acceptance)
    dash = client.get(f"{API}/dashboard", params={"project_id": p["id"]}).json()
    ex = dash["executions"]
    assert ex["total"] == len(run["executions"]) == 2
    assert (ex["passed"], ex["failed"]) == (1, 1) and dash["pass_rate"] == 0.5
    assert dash["findings"]["open"] == sum(dash["findings"]["open_by_severity"].values()) == 1
    assert sum(d["passed"] + d["failed"] + d["other"] for d in dash["trend"]) == 2
    assert dash["projects"] == 1 and dash["scans"] == 1
    assert client.get(f"{API}/dashboard").json()["projects"] >= 1  # global scope works too

    # Map overlays tests and open findings per page
    nodes = {n["url"].rstrip("/").split("/", 3)[-1]: n for n in client.get(f"{API}/discovery/{scan_id}/map").json()["nodes"]}
    assert nodes["users/new"]["open_findings"] == 1 and nodes["users/new"]["tests"] >= 1

    # Scan report: self-contained HTML with config, results, evidence and limitations
    r = client.get(f"{API}/scan-runs/{scan_id}/report")
    html = r.text
    for needle in ("Scan configuration", d1["title"], "data:image/png;base64,", "Limitations", "hypothesis"):
        assert needle in html, needle
    dl = client.get(f"{API}/scan-runs/{scan_id}/report", params={"download": True})
    assert "attachment" in dl.headers["content-disposition"]

    # Versions: generation is v1; an edit is v2 and needs re-approval
    vs = client.get(f"{API}/test-cases/{home['id']}/versions").json()
    assert [v["version"] for v in vs] == [1] and vs[0]["source"] == "generated:rules"
    d = client.get(f"{API}/test-cases/{home['id']}").json()["definition_json"]
    d["title"] = "Home page loads (edited)"
    edited = client.patch(f"{API}/test-cases/{home['id']}", json={"definition": d}).json()
    assert (edited["version"], edited["status"], edited["title"]) == (2, "draft", "Home page loads (edited)")
    vs = client.get(f"{API}/test-cases/{home['id']}/versions").json()
    assert [(v["version"], v["source"]) for v in vs] == [(2, "edited"), (1, "generated:rules")]

    # Duplicate makes an independent draft copy
    dup = client.post(f"{API}/test-cases/{home['id']}/duplicate").json()
    assert dup["id"] != home["id"] and dup["key"].endswith("-COPY") and dup["status"] == "draft"

    # Regenerate needs the AI planner; without a key it says so instead of faking it
    r = client.post(f"{API}/test-cases/{home['id']}/regenerate", json={"instructions": "also check the nav"})
    assert r.status_code == 409 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_publish_is_noop_without_redis():
    events.publish("p1", "scan.started", scan_id="s1")  # eager mode: must not raise or block
