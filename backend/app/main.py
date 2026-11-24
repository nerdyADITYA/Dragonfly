import asyncio
import contextlib
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.events import channel
from app.reports import router as reports_router
from app.routes import router
from app.routes_findings import router as findings_router

app = FastAPI(title="Dragonfly", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(findings_router)
app.include_router(reports_router)


@app.websocket("/api/v1/ws/projects/{project_id}")
async def project_events(ws: WebSocket, project_id: uuid.UUID):
    """Forwards the project's live events. shortcut: unauthenticated like the REST API until Phase 1."""
    import redis.asyncio as aioredis

    await ws.accept()
    client = aioredis.Redis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(project_id))

    async def forward():
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws.send_text(msg["data"].decode())

    async def drain():  # returns when the browser disconnects
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                await ws.receive_text()

    try:
        tasks = [asyncio.create_task(forward()), asyncio.create_task(drain())]
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
    finally:
        await pubsub.aclose()
        await client.aclose()


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"status": "ok", "ai": "claude" if settings.anthropic_api_key else "rules-only"}
