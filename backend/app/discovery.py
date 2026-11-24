"""Application Explorer (§8). Breadth-first crawl of in-scope links; records pages, elements, forms, edges.

Milestone A scope: follows links only. It never submits forms or clicks buttons, so it has no side
effects beyond GET requests, and it skips links whose text/URL looks destructive.
"""
import re
import time
from collections import deque
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app import storage
from app.api_testing import record_network_calls
from app.browser import isolated_page, screenshot
from app.events import publish
from app.models import (
    ApplicationEdge,
    AuditLog,
    DiscoveredElement,
    DiscoveredForm,
    DiscoveredPage,
    Environment,
    ScanRun,
)
from app.schemas import ScanPolicy
from app.scope import DESTRUCTIVE_RE, ScopeError, check_url, in_scope
from app.target_auth import login_path, session_state

EXTRACT_JS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const labelOf = el => {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText.trim(); }
    const wrap = el.closest('label'); if (wrap) return wrap.innerText.trim();
    return '';
  };
  const roleOf = el => el.getAttribute('role') || ({A:'link',BUTTON:'button',SELECT:'combobox',TEXTAREA:'textbox'}[el.tagName]
    || (el.tagName === 'INPUT' ? ({checkbox:'checkbox',radio:'radio',submit:'button',button:'button'}[el.type] || 'textbox') : el.tagName.toLowerCase()));
  const nameOf = el => (el.getAttribute('aria-label') || labelOf(el) || el.innerText || el.value || el.placeholder || el.title || '').trim().slice(0, 200);
  const elements = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab]')]
    .slice(0, 300).map(el => ({
      tag: el.tagName.toLowerCase(), role: roleOf(el), name: nameOf(el), label: labelOf(el),
      type: el.type || null, href: el.tagName === 'A' ? el.href : null, placeholder: el.placeholder || null,
      test_id: el.getAttribute('data-testid'), id: el.id || null, required: !!el.required, visible: vis(el),
    }));
  const forms = [...document.forms].slice(0, 30).map((f, i) => {
    const submit = f.querySelector('button[type=submit],button:not([type]),input[type=submit]');
    return {
      name: f.getAttribute('aria-label') || f.getAttribute('name') || f.id || `form-${i + 1}`,
      method: (f.getAttribute('method') || 'get').toLowerCase(), action: f.action,
      submit_label: submit ? (submit.innerText || submit.value || '').trim() : '',
      fields: [...f.elements].filter(e => e.name && e.type !== 'hidden' && e.tagName !== 'BUTTON' && e.type !== 'submit')
        .map(e => ({ name: e.name, type: e.type, label: labelOf(e), required: !!e.required, placeholder: e.placeholder || null })),
    };
  });
  return { title: document.title, elements, forms };
}
"""

_ID_SEG = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f-]{27,}|[0-9a-f]{24,})$", re.IGNORECASE)


def normalize(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", p.query, ""))


def route_pattern(url: str) -> str:
    """/users/42?page=2 → /users/{id}?page — repeated routes collapse into one page (§8.6)."""
    p = urlsplit(url)
    path = "/".join("{id}" if _ID_SEG.match(s) else s for s in p.path.rstrip("/").split("/")) or "/"
    keys = sorted({kv.split("=")[0] for kv in p.query.split("&") if kv})
    return path + ("?" + "&".join(keys) if keys else "")


def selector_candidates(el: dict) -> list[dict]:
    """Ordered by the plan's selector priority (§21.3)."""
    c = []
    if el["role"] and el["name"]:
        c.append({"role": el["role"], "name": el["name"]})
    if el["label"]:
        c.append({"label": el["label"]})
    if el["placeholder"]:
        c.append({"placeholder": el["placeholder"]})
    if el["test_id"]:
        c.append({"test_id": el["test_id"]})
    if el["id"]:
        c.append({"css": f"#{el['id']}"})
    return c


def _log(db, scan, msg, severity="info", **meta):
    db.add(AuditLog(project_id=scan.project_id, scan_run_id=scan.id, source="discovery", severity=severity,
                    message=msg, metadata_json=meta))


def run_discovery(db: Session, scan_id) -> None:
    scan = db.get(ScanRun, scan_id)
    env = db.get(Environment, scan.environment_id)
    policy = ScanPolicy(**scan.scan_policy_snapshot)
    base = env.base_url
    scan.status, scan.stage, scan.started_at = "running", "discovery", datetime.now(UTC)
    db.commit()
    publish(scan.project_id, "scan.started", scan_id=scan.id)

    deadline = time.monotonic() + policy.max_duration_seconds
    seen: dict[str, DiscoveredPage] = {}  # route pattern → page
    queue = deque([(normalize(base), 0, None, "initial")])
    stats = {"pages": 0, "elements": 0, "forms": 0, "skipped_destructive": 0, "skipped_out_of_scope": 0,
             "errors": 0, "stopped_reason": "exhausted", "authenticated": False, "login_redirects": 0}
    skipped: list[dict] = []
    rejected: set[str] = set()  # each unsafe/out-of-scope URL is recorded once

    try:
        state = session_state(db, env)  # signs in first when the environment has a login profile
        stats["authenticated"] = state is not None
        lpath = login_path(db, env)
        if state:
            _log(db, scan, "signed in to the target with the environment's login profile")
        with isolated_page(base, policy, storage_state=state) as (page, _ctx, events):
            while queue:
                db.refresh(scan)
                if scan.cancel_requested:
                    stats["stopped_reason"] = "cancelled"
                    break
                if time.monotonic() > deadline:
                    stats["stopped_reason"] = "max_duration"
                    break
                if stats["pages"] >= policy.max_pages:
                    stats["stopped_reason"] = "max_pages"
                    break
                url, depth, parent, trigger = queue.popleft()
                if route_pattern(url) in seen:
                    if parent:
                        db.add(ApplicationEdge(scan_run_id=scan.id, source_page_id=parent.id,
                                               destination_page_id=seen[route_pattern(url)].id, trigger=trigger))
                    continue
                try:
                    check_url(url, base, policy)
                    resp = page.goto(url, wait_until="load")
                    final = normalize(page.url)
                    if final != url:
                        check_url(final, base, policy)  # redirects must stay in scope too
                    data = page.evaluate(EXTRACT_JS)
                    shot = storage.save(db, screenshot(page), project_id=scan.project_id, artifact_type="screenshot",
                                        mime="image/png", ext="png", scan_run_id=scan.id)
                except ScopeError as e:
                    stats["skipped_out_of_scope"] += 1
                    skipped.append({"url": url, "reason": str(e)})
                    _log(db, scan, f"blocked navigation to {url}: {e}", "warning")
                    continue
                except Exception as e:  # navigation error on one page should not kill the scan
                    stats["errors"] += 1
                    _log(db, scan, f"failed to load {url}: {str(e)[:300]}", "error")
                    continue

                fpath, upath = urlsplit(final).path.rstrip("/") or "/", urlsplit(url).path.rstrip("/") or "/"
                if lpath and fpath == lpath != upath:  # bounced to login: session lost or page needs another role
                    stats["login_redirects"] += 1
                    _log(db, scan, f"{url} redirected to the login page (session expired or insufficient role)", "warning")
                pattern = route_pattern(final)
                if pattern in seen:  # redirected onto an already-known page
                    continue
                dp = DiscoveredPage(scan_run_id=scan.id, parent_page_id=parent.id if parent else None, url=final,
                                    route_pattern=pattern, title=data["title"][:500],
                                    status_code=resp.status if resp else None, depth=depth,
                                    discovery_source=trigger if trigger == "initial" else "link",
                                    screenshot_artifact_id=shot.id)
                db.add(dp)
                db.flush()
                seen[pattern] = seen[route_pattern(url)] = dp
                if parent:
                    db.add(ApplicationEdge(scan_run_id=scan.id, source_page_id=parent.id, destination_page_id=dp.id,
                                           trigger=trigger))
                for el in data["elements"]:
                    db.add(DiscoveredElement(discovered_page_id=dp.id, element_type=el["role"],
                                             accessible_name=el["name"], is_visible=el["visible"],
                                             selector_candidates_json=selector_candidates(el),
                                             attributes_json={k: el[k] for k in ("tag", "type", "href", "required") if el[k]}))
                for f in data["forms"]:
                    db.add(DiscoveredForm(discovered_page_id=dp.id, name=f["name"][:200], method=f["method"],
                                          action=f["action"][:2000], fields_json=f["fields"],
                                          submit_label=f["submit_label"][:200]))
                stats["pages"] += 1
                stats["elements"] += len(data["elements"])
                stats["forms"] += len(data["forms"])
                db.commit()
                publish(scan.project_id, "discovery.page_found", scan_id=scan.id, url=final, pages=stats["pages"])

                if depth >= policy.max_depth:
                    continue
                for el in data["elements"]:
                    href = el["href"]
                    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                        continue
                    target = normalize(urljoin(final, href))
                    if target in rejected:
                        continue
                    kind = reason = None
                    if DESTRUCTIVE_RE.search(f"{el['name']} {urlsplit(target).path.replace('/', ' ')}"):
                        kind, reason = "skipped_destructive", f"destructive-looking link {el['name']!r}"
                    else:
                        try:
                            check_url(target, base, policy)
                        except ScopeError as e:
                            kind, reason = "skipped_out_of_scope", str(e)
                    if kind:
                        rejected.add(target)
                        stats[kind] += 1
                        skipped.append({"url": target, "reason": reason})
                        continue
                    if route_pattern(target) not in seen:
                        queue.append((target, depth + 1, dp, el["name"][:500]))
            events_summary = events.as_dict()
            api_calls = {c for c in events.api_calls if in_scope(c[1], base, policy)}

        scan.status = "cancelled" if stats["stopped_reason"] == "cancelled" else "completed"
        stats["api_endpoints_seen"] = record_network_calls(db, env, api_calls)
        scan.summary_json = {**stats, "skipped": skipped[:100], "browser_events": events_summary,
                             "limitations": ["Links only: buttons and forms were not exercised during discovery.",
                                             "Signed in with the environment login profile." if stats["authenticated"] else "Unauthenticated crawl: add a login profile to explore pages behind sign-in."]}
    except Exception as e:
        db.rollback()
        scan = db.get(ScanRun, scan_id)
        scan.status, scan.error_message = "failed", f"{type(e).__name__}: {str(e)[:1000]}"
        scan.summary_json = stats
    scan.stage = "done"
    scan.completed_at = datetime.now(UTC)
    db.commit()
    publish(scan.project_id, f"scan.{scan.status}", scan_id=scan.id, pages=stats["pages"])
