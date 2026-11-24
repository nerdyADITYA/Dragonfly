"""Authenticated scanning: encrypted login profile → signed-in discovery, browser and API tests."""
import uuid

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuthProfile

API = "/api/v1"
DEMO_LOGIN = {"username": "demo@acme.test", "password": "demo-password"}


def _env(client, demo_url, name):
    p = client.post(f"{API}/projects", json={"name": name}).json()
    env = client.post(f"{API}/projects/{p['id']}/environments", json={
        "name": "local", "base_url": demo_url, "authorization_confirmed": True,
        "scan_policy": {"allow_private_network": True, "max_pages": 15, "max_depth": 2, "requests_per_second": 50}}).json()
    return p, env


def _discover(client, p, env):
    scan = client.post(f"{API}/projects/{p['id']}/discovery", json={"environment_id": env["id"]}).json()
    return client.get(f"{API}/discovery/{scan['id']}").json()


def test_login_profile_is_encrypted_and_testable(client, demo):
    _, env = _env(client, demo.url, "Profile")
    url = f"{API}/environments/{env['id']}/auth-profile"
    assert client.put(url, json={"login_url": demo.url + "login", "username": "x"}).status_code == 422  # needs pw
    r = client.put(url, json={"login_url": "https://example.com/login", **DEMO_LOGIN})
    assert r.status_code == 422 and "scope" in r.json()["detail"]
    saved = client.put(url, json={"login_url": demo.url + "login", **DEMO_LOGIN}).json()
    assert "password" not in saved and saved["has_password"]
    with SessionLocal() as db:
        raw = db.scalars(select(AuthProfile).where(AuthProfile.environment_id == uuid.UUID(env["id"]))).one().password_encrypted
    assert "demo-password" not in raw

    assert client.post(f"{url}/test").json()["ok"] is True
    client.put(url, json={"login_url": demo.url + "login", "username": "demo@acme.test", "password": "wrong"})
    bad = client.post(f"{url}/test").json()
    assert bad["ok"] is False and "still on /login" in bad["message"]
    # update without a password keeps the stored one
    client.put(url, json={"login_url": demo.url + "login", **DEMO_LOGIN})
    client.put(url, json={"login_url": demo.url + "login", "username": "demo@acme.test", "enabled": True})
    assert client.post(f"{url}/test").json()["ok"] is True


def test_signed_in_discovery_reaches_protected_pages(client, demo):
    p, env = _env(client, demo.url, "Anon")
    anon = _discover(client, p, env)
    anon_urls = {pg["url"] for pg in client.get(f"{API}/discovery/{anon['id']}/pages").json()}
    assert not any("/account" in u for u in anon_urls) and anon["summary_json"]["authenticated"] is False

    client.put(f"{API}/environments/{env['id']}/auth-profile", json={"login_url": demo.url + "login", **DEMO_LOGIN})
    scan = _discover(client, p, env)
    assert scan["status"] == "completed" and scan["summary_json"]["authenticated"] is True
    urls = {pg["url"] for pg in client.get(f"{API}/discovery/{scan['id']}/pages").json()}
    assert {demo.url + "account", demo.url + "account/settings"} <= urls

    # Browser test for a protected page and API test for a protected endpoint both run signed in
    client.post(f"{API}/environments/{env['id']}/openapi", json={"url": demo.url + "openapi.json"})
    client.post(f"{API}/projects/{p['id']}/tests/generate", json={"scan_run_id": scan["id"]})
    gen = client.post(f"{API}/projects/{p['id']}/tests/generate-api", json={"scan_run_id": scan["id"]}).json()
    assert gen["authenticated"] is True
    tests = client.get(f"{API}/projects/{p['id']}/test-cases").json()
    pick = [t for t in tests if t["title"].startswith("My account") or t["title"] == "GET /api/me responds with 2xx"]
    assert len(pick) == 2
    for t in pick:
        client.post(f"{API}/test-cases/{t['id']}/approve")
    run = client.post(f"{API}/test-runs", json={"environment_id": env["id"], "test_case_ids": [t["id"] for t in pick]})
    run = client.get(f"{API}/test-runs/{run.json()['id']}").json()
    assert [e["status"] for e in run["executions"]] == ["passed", "passed"], run["executions"]

    # A broken login blocks the run instead of reporting false failures
    client.put(f"{API}/environments/{env['id']}/auth-profile",
               json={"login_url": demo.url + "login", "username": "demo@acme.test", "password": "wrong"})
    run = client.post(f"{API}/test-runs", json={"environment_id": env["id"], "test_case_ids": [pick[0]["id"]]})
    ex = client.get(f"{API}/test-runs/{run.json()['id']}").json()["executions"][0]
    assert (ex["status"], ex["failure_type"]) == ("blocked", "auth")
    assert not client.get(f"{API}/projects/{p['id']}/findings").json()


def test_protected_endpoints_skipped_without_profile(client, demo):
    p, env = _env(client, demo.url, "NoProfile")
    scan = _discover(client, p, env)
    client.post(f"{API}/environments/{env['id']}/openapi", json={"url": demo.url + "openapi.json"})
    eps = {e["path"]: e for e in client.get(f"{API}/environments/{env['id']}/endpoints").json()}
    assert "/api/me" in eps
    gen = client.post(f"{API}/projects/{p['id']}/tests/generate-api", json={"scan_run_id": scan["id"]}).json()
    assert any(s["endpoint"] == "GET /api/me" and "sign-in" in s["reason"] for s in gen["skipped_endpoints"])
