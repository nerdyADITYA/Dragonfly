"""Phase 1: sign-in, sessions, roles, tenant isolation, CSRF guard, password storage."""
from app.auth import hash_password, verify_password
from app.db import SessionLocal
from app.models import Organization, OrganizationMember, User
from tests.conftest import OWNER

API = "/api/v1"


def _login(c, email, password):
    return c.post(f"{API}/auth/login", json={"email": email, "password": password})


def test_passwords_are_hashed_and_verified():
    h = hash_password("correct horse battery")
    assert h.startswith("scrypt$") and "correct horse" not in h
    assert verify_password("correct horse battery", h) and not verify_password("wrong", h)
    assert hash_password("same") != hash_password("same")  # salted


def test_signed_out_requests_are_refused(client, new_client):
    anon = new_client()
    assert anon.get(f"{API}/projects").status_code == 401
    assert anon.get(f"{API}/dashboard").status_code == 401
    assert anon.get(f"{API}/auth/status").json() == {"setup_required": False}
    assert anon.post(f"{API}/auth/register", json={**OWNER, "email": "x@y.z"}).status_code == 403  # setup done
    assert client.get(f"{API}/auth/me").json()["role"] == "owner"


def test_login_logout_and_throttling(client, new_client):
    c = new_client()
    assert _login(c, OWNER["email"], "nope-nope-nope").status_code == 401
    assert _login(c, OWNER["email"].upper(), OWNER["password"]).status_code == 200  # email is case-insensitive
    assert c.get(f"{API}/projects").status_code == 200
    assert c.post(f"{API}/auth/logout").status_code == 204
    assert c.get(f"{API}/projects").status_code == 401  # session revoked server-side

    t = new_client()
    for _ in range(5):
        assert _login(t, "ghost@dragonfly.test", "wrong-password-x").status_code == 401
    assert _login(t, "ghost@dragonfly.test", "wrong-password-x").status_code == 429


def test_roles(client, new_client):
    r = client.post(f"{API}/org/members", json={"email": "vic@dragonfly.test", "display_name": "Vic Viewer",
                                                "role": "viewer", "password": "viewer-password-1"})
    assert r.status_code == 201
    client.post(f"{API}/org/members", json={"email": "meg@dragonfly.test", "display_name": "Meg Member",
                                            "role": "member", "password": "member-password-1"})
    p = client.post(f"{API}/projects", json={"name": "Roles"}).json()

    viewer = new_client()
    _login(viewer, "vic@dragonfly.test", "viewer-password-1")
    assert viewer.get(f"{API}/projects/{p['id']}").status_code == 200
    assert viewer.post(f"{API}/projects", json={"name": "x"}).status_code == 403
    assert viewer.patch(f"{API}/findings/00000000-0000-0000-0000-000000000000", json={}).status_code == 403

    member = new_client()
    _login(member, "meg@dragonfly.test", "member-password-1")
    assert member.post(f"{API}/projects", json={"name": "x"}).status_code == 403  # admin-only
    assert member.post(f"{API}/org/members", json={"email": "a@b.c", "display_name": "a", "role": "viewer",
                                                   "password": "0123456789"}).status_code == 403
    me = client.get(f"{API}/auth/me").json()
    assert client.patch(f"{API}/org/members/{me['id']}", json={"role": "admin"}).status_code == 409  # last owner


def test_tenant_isolation(client, new_client):
    mine = client.post(f"{API}/projects", json={"name": "Private"}).json()
    with SessionLocal() as db:  # a second organization with its own owner
        org = Organization(name="Other Co")
        user = User(email="eve@other.test", display_name="Eve", password_hash=hash_password("eve-password-1"))
        db.add_all([org, user])
        db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        db.commit()
    eve = new_client()
    _login(eve, "eve@other.test", "eve-password-1")
    assert all(p["id"] != mine["id"] for p in eve.get(f"{API}/projects").json())
    assert eve.get(f"{API}/projects/{mine['id']}").status_code == 404           # URL id
    assert eve.delete(f"{API}/projects/{mine['id']}").status_code == 404
    assert eve.get(f"{API}/dashboard", params={"project_id": mine["id"]}).status_code == 404
    env = client.post(f"{API}/projects/{mine['id']}/environments", json={
        "name": "e", "base_url": "https://example.com/", "authorization_confirmed": True}).json()
    theirs = eve.post(f"{API}/projects", json={"name": "Eve's"}).json()
    # body id pointing at another tenant's environment
    r = eve.post(f"{API}/projects/{theirs['id']}/discovery", json={"environment_id": env["id"]})
    assert r.status_code == 404
    assert client.get(f"{API}/projects/{mine['id']}").status_code == 200


def test_cross_site_writes_are_refused(client):
    r = client.post(f"{API}/projects", json={"name": "csrf"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    ok = client.post(f"{API}/projects", json={"name": "same-site"}, headers={"Origin": "http://testserver"})
    assert ok.status_code == 201
