from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routes import router
from app.routes_findings import router as findings_router

app = FastAPI(title="Dragonfly", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(findings_router)


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("select 1"))
    return {"status": "ok", "ai": "claude" if settings.anthropic_api_key else "rules-only"}
