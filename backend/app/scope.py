"""Target scope + SSRF guard (§29.2, §29.3). Every URL a scan touches goes through `check_url`."""
import ipaddress
import re
import socket
from functools import lru_cache
from urllib.parse import urlsplit

from app.config import settings
from app.schemas import ScanPolicy

# Words that mark an action/link as having real-world side effects (§8.4, §29.4).
DESTRUCTIVE_RE = re.compile(
    r"\b(delete|remove|destroy|purge|drop|purchase|buy|checkout|pay|order|transfer|send|publish|"
    r"invite|unsubscribe|deactivate|cancel account|change password|reset password|logout|log out|sign out)\b",
    re.IGNORECASE,
)


class ScopeError(Exception):
    pass


def effective_domains(base_url: str, policy: ScanPolicy) -> list[str]:
    return [d.lower() for d in policy.allowed_domains] or [urlsplit(base_url).hostname.lower()]


def host_allowed(host: str, domains: list[str]) -> bool:
    host = host.lower()
    for d in domains:
        if d.startswith("*.") and (host == d[2:] or host.endswith(d[1:])):
            return True
        if host == d:
            return True
    return False


@lru_cache(maxsize=512)
def _resolve(host: str) -> tuple[str, ...]:
    # shortcut: cached forever per process, so DNS rebinding mid-scan isn't caught; add TTL before multi-tenant use.
    try:
        return tuple({info[4][0] for info in socket.getaddrinfo(host, None)})
    except socket.gaierror as e:
        raise ScopeError(f"cannot resolve host {host!r}") from e


def _ip_blocked(ip: str, allow_private: bool) -> str | None:
    addr = ipaddress.ip_address(ip.split("%")[0])
    if addr.is_link_local or str(addr) in ("169.254.169.254", "fd00:ec2::254"):
        return "link-local / cloud metadata address"
    if addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return "reserved address"
    if (addr.is_private or addr.is_loopback) and not allow_private:
        return "private/loopback address (enable allow_private_network for local targets)"
    return None


def check_url(url: str, base_url: str, policy: ScanPolicy, resolve: bool = True) -> None:
    """Raise ScopeError if `url` is outside the authorized scope."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ScopeError(f"scheme {parts.scheme!r} not allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise ScopeError("missing host")
    if host in settings.blocked_hosts:
        raise ScopeError(f"host {host!r} is a Dragonfly control-plane service")
    if not host_allowed(host, effective_domains(base_url, policy)):
        raise ScopeError(f"host {host!r} not in allowed domains")
    path = parts.path or "/"
    for prefix in policy.excluded_paths:
        if path.startswith(prefix):
            raise ScopeError(f"path {path!r} is excluded ({prefix})")
    if resolve:
        try:
            ips = (host,) if ipaddress.ip_address(host) else ()
        except ValueError:
            ips = _resolve(host)
        for ip in ips:
            if reason := _ip_blocked(ip, policy.allow_private_network):
                raise ScopeError(f"{host} resolves to {ip}: {reason}")


def in_scope(url: str, base_url: str, policy: ScanPolicy) -> bool:
    try:
        check_url(url, base_url, policy)
        return True
    except ScopeError:
        return False
