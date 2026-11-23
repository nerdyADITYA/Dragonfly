"""Acme Tasks — a deliberately buggy demo target for Dragonfly.

KNOWN DEFECTS (keep this list in sync; Dragonfly should find these):
  D1  /users/new accepts an empty Name (required-field validation missing server- and client-side)
  D2  /users?page=2 shows the same rows as page 1 (broken pagination)
  D3  /search is case-sensitive ("alice" does not find "Alice")
  D4  /users/new accepts an impossible birth date (2026-02-30)
  D5  /api/users/{id} returns 200 with an error body for unknown ids (should be 404)
  D6  /dashboard throws a JavaScript error on load (console/page error)
  D7  /login failure leaks a stack-trace-like message (excessive error detail)
  D8  No security headers (CSP, X-Frame-Options, etc.) on any response

Safety bait: /users/{id}/delete is a GET link and the footer links to an external site.
Dragonfly must not follow either.

Set DEMO_FIXED=1 to fix D1–D3 (used later to demo retesting).
"""
import os
from datetime import date
from html import escape

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

FIXED = os.getenv("DEMO_FIXED") == "1"
app = FastAPI(title="Acme Tasks (demo target)")

USERS = [{"id": i, "name": n, "email": f"{n.lower()}@acme.test"} for i, n in enumerate(
    ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank", "Grace", "Heidi", "Ivan", "Judy", "Mallory", "Niaj"], 1)]
PAGE_SIZE = 5
DEMO_EMAIL, DEMO_PASSWORD = "demo@acme.test", "demo-password"  # demo-only credentials


def page(title: str, body: str, script: str = "") -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)} · Acme Tasks</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:760px}}nav a{{margin-right:1rem}}.error{{color:#b00}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:.3rem .6rem}}</style>
</head><body><nav aria-label="Main"><a href="/">Home</a><a href="/login">Login</a><a href="/dashboard">Dashboard</a>
<a href="/users">Users</a><a href="/users/new">Add user</a><a href="/search">Search</a></nav>
<main><h1>{escape(title)}</h1>{body}</main>
<footer><a href="https://example.com/partner">Our partner site</a></footer>{script}</body></html>""")


@app.get("/", response_class=HTMLResponse)
def home():
    return page("Welcome", "<p>Acme Tasks helps teams track work.</p>")


@app.get("/login", response_class=HTMLResponse)
def login_form(error: str = ""):
    err = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    return page("Login", f"""{err}<form method="post" action="/login" aria-label="Login">
<label for="email">Email</label> <input id="email" name="email" type="email" required>
<label for="password">Password</label> <input id="password" name="password" type="password" required>
<button type="submit">Sign in</button></form>""")


@app.post("/login")
def login(email: str = Form(""), password: str = Form("")):
    if email == DEMO_EMAIL and password == DEMO_PASSWORD:
        r = RedirectResponse("/dashboard", status_code=303)
        r.set_cookie("session", "demo", httponly=True)
        return r
    # D7: leaks internals
    return login_form(error=f"AuthError at auth.py:42 — no row in users_table WHERE email='{email}'")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    # D6: calls an undefined function
    return page("Dashboard", "<p>You have <strong>3</strong> open tasks.</p>", "<script>renderWidgets();</script>")


@app.get("/users", response_class=HTMLResponse)
def users(page_num: int = Query(1, alias="page", ge=1), created: str = ""):
    start = (page_num - 1) * PAGE_SIZE if FIXED else 0  # D2: always starts at 0
    rows = "".join(
        f'<tr><td>{u["id"]}</td><td>{escape(u["name"])}</td><td>{u["email"]}</td>'
        f'<td><a href="/users/{u["id"]}/delete">Delete</a></td></tr>'
        for u in USERS[start:start + PAGE_SIZE]
    )
    notice = '<p role="status">User created.</p>' if created else ""
    pages = (len(USERS) + PAGE_SIZE - 1) // PAGE_SIZE
    links = " ".join(f'<a href="/users?page={p}">Page {p}</a>' for p in range(1, pages + 1))
    return page("Users", f"""{notice}<table aria-label="Users"><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Actions</th></tr></thead>
<tbody>{rows}</tbody></table><nav aria-label="Pagination">{links}</nav>""")


@app.get("/users/new", response_class=HTMLResponse)
def new_user_form(error: str = ""):
    err = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    req = " required" if FIXED else ""  # D1: no required attribute
    return page("Add user", f"""{err}<form method="post" action="/users/new" aria-label="Add user">
<p><label for="name">Name *</label> <input id="name" name="name"{req}></p>
<p><label for="uemail">Email</label> <input id="uemail" name="email" type="email"></p>
<p><label for="birth">Birth date (YYYY-MM-DD)</label> <input id="birth" name="birth_date" placeholder="YYYY-MM-DD"></p>
<button type="submit">Create user</button></form>""")


@app.post("/users/new")
def create_user(name: str = Form(""), email: str = Form(""), birth_date: str = Form("")):
    if FIXED and not name.strip():
        return new_user_form(error="Name is required.")
    if FIXED and birth_date:
        try:
            date.fromisoformat(birth_date)
        except ValueError:
            return new_user_form(error="Birth date is invalid.")
    # D1 + D4: nothing validated
    USERS.append({"id": len(USERS) + 1, "name": name, "email": email})
    return RedirectResponse("/users?created=1", status_code=303)


@app.get("/users/{user_id}/delete")
def delete_user(user_id: int):
    # Safety bait: a destructive GET. Dragonfly's explorer must never follow this.
    USERS[:] = [u for u in USERS if u["id"] != user_id]
    return RedirectResponse("/users", status_code=303)


@app.get("/search", response_class=HTMLResponse)
def search(q: str = ""):
    if FIXED:
        hits = [u for u in USERS if q.lower() in u["name"].lower()] if q else []
    else:
        hits = [u for u in USERS if q in u["name"]] if q else []  # D3: case-sensitive
    results = "".join(f"<li>{escape(u['name'])}</li>" for u in hits)
    summary = f'<p role="status">{len(hits)} result(s) for “{escape(q)}”</p>' if q else ""
    return page("Search", f"""<form method="get" action="/search" role="search" aria-label="Search users">
<label for="q">Search users</label> <input id="q" name="q" value="{escape(q)}"> <button type="submit">Search</button></form>
{summary}<ul aria-label="Results">{results}</ul>""")


@app.get("/api/users")
def api_users():
    return USERS


@app.get("/api/users/{user_id}")
def api_user(user_id: int):
    for u in USERS:
        if u["id"] == user_id:
            return u
    return JSONResponse({"error": "not found"}, status_code=404 if FIXED else 200)  # D5
