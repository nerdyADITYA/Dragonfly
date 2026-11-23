import pytest

from app.schemas import Action, ScanPolicy, Target, TestCaseDef
from app.scope import ScopeError, check_url
from app.validator import fingerprint, validate

BASE = "http://127.0.0.1:8001/"
LOCAL = ScanPolicy(allow_private_network=True, excluded_paths=["/admin"])


@pytest.mark.parametrize("url,reason", [
    ("https://example.com/", "not in allowed domains"),
    ("http://127.0.0.1:8001/admin/users", "excluded"),
    ("ftp://127.0.0.1/", "scheme"),
    ("http://redis:6379/", "control-plane"),
])
def test_scope_blocks(url, reason):
    with pytest.raises(ScopeError, match=reason):
        check_url(url, BASE, LOCAL)


def test_private_ip_needs_explicit_opt_in():
    with pytest.raises(ScopeError, match="private/loopback"):
        check_url(BASE, BASE, ScanPolicy())
    check_url(BASE + "users", BASE, LOCAL)  # allowed once opted in


def test_metadata_ip_always_blocked():
    pol = ScanPolicy(allowed_domains=["169.254.169.254"], allow_private_network=True)
    with pytest.raises(ScopeError, match="metadata"):
        check_url("http://169.254.169.254/latest/meta-data", "http://169.254.169.254/", pol)


def test_wildcard_subdomains():
    pol = ScanPolicy(allowed_domains=["*.acme.test"], allow_private_network=True)
    check_url("http://app.acme.test/", "http://app.acme.test/", pol, resolve=False)
    with pytest.raises(ScopeError):
        check_url("http://acme.test.evil.com/", "http://app.acme.test/", pol, resolve=False)


def _test(*steps, **kw):
    base = {"key": "T-1", "title": "t", "category": "functional", "priority": "P2", "target_url": BASE}
    return TestCaseDef(steps=list(steps), **(base | kw))


NAV = Action(type="navigate", url=BASE)
ASSERT = Action(type="assert_title", value="Welcome")


def test_valid_test_passes():
    assert validate(_test(NAV, ASSERT), BASE, LOCAL) == []


def test_requires_assertion():
    assert any("no assertions" in e for e in validate(_test(NAV), BASE, LOCAL))


def test_blocks_destructive_click_and_out_of_scope_navigation():
    errs = validate(_test(NAV, Action(type="click", target=Target(role="button", name="Delete account")),
                          Action(type="navigate", url="https://evil.example/"), ASSERT), BASE, LOCAL)
    assert any("destructive" in e for e in errs)
    assert any("out of scope" in e for e in errs)


def test_missing_required_fields():
    errs = validate(_test(NAV, Action(type="fill", target=Target(label="Name")), ASSERT), BASE, LOCAL)
    assert any("missing value" in e for e in errs)


def test_destructive_side_effect_blocked_by_default():
    assert any("destructive" in e for e in validate(_test(NAV, ASSERT, side_effect="destructive"), BASE, LOCAL))


def test_fingerprint_ignores_wording():
    a = _test(NAV, ASSERT)
    b = _test(NAV.model_copy(update={"description": "different words"}), ASSERT, title="other title")
    assert fingerprint(a) == fingerprint(b)
