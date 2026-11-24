"""Live progress events (§27.10): worker → Redis pub/sub → API WebSocket → browser.

Payloads carry ids, counters and status only — never secrets or response bodies.
"""
import json
import logging
from datetime import UTC, datetime
from functools import lru_cache

import redis

from app.config import settings

log = logging.getLogger(__name__)


def channel(project_id) -> str:
    return f"events:{project_id}"


@lru_cache(maxsize=1)
def _client():
    return redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)


def publish(project_id, event_type: str, **data) -> None:
    """Best effort: a missed event only delays the UI (it also refetches), so never break the job."""
    if settings.celery_eager:  # inline mode (tests/dev) has no Redis
        return
    msg = {"type": event_type, "project_id": str(project_id), "ts": datetime.now(UTC).isoformat(),
           **{k: str(v) if v is not None and not isinstance(v, int | float | bool) else v for k, v in data.items()}}
    try:
        _client().publish(channel(project_id), json.dumps(msg))
    except redis.RedisError:
        log.warning("could not publish %s", event_type)
