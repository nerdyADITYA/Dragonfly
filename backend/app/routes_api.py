"""API inventory + API/security test generation (§11, §12). Same no-auth shortcut as routes.py."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import api_testing
from app.db import get_db
from app.models import AuditLog, DiscoveredEndpoint, Environment, ScanRun
from app.routes import get_or_404
from app.schemas import EndpointOut, GenerateApiTestsIn, OpenApiImportIn
from app.scope import ScopeError

router = APIRouter(prefix="/api/v1")


@router.post("/environments/{env_id}/openapi")
def import_openapi(env_id: uuid.UUID, body: OpenApiImportIn, db: Session = Depends(get_db)):
    env = get_or_404(db, Environment, env_id)
    if not env.authorization_confirmed:
        raise HTTPException(409, "Confirm you are authorized to test this environment first")
    if bool(body.url) == bool(body.spec):
        raise HTTPException(422, "Provide exactly one of `url` or `spec`")
    try:
        spec = api_testing.fetch_spec(env, body.url) if body.url else body.spec
        result = api_testing.import_openapi(db, env, spec)
    except ScopeError as e:
        raise HTTPException(422, f"spec URL rejected by scope policy: {e}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # network errors fetching the spec
        raise HTTPException(502, f"could not fetch spec: {type(e).__name__}")
    db.add(AuditLog(project_id=env.project_id, source="api", message=f"OpenAPI imported for {env.name}",
                    metadata_json={**result, "url": body.url}))
    db.commit()
    return result


@router.get("/environments/{env_id}/endpoints", response_model=list[EndpointOut])
def list_endpoints(env_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(select(DiscoveredEndpoint).where(DiscoveredEndpoint.environment_id == env_id)
                      .order_by(DiscoveredEndpoint.path, DiscoveredEndpoint.method)).all()


@router.post("/projects/{project_id}/tests/generate-api")
def generate_api_tests(project_id: uuid.UUID, body: GenerateApiTestsIn, db: Session = Depends(get_db)):
    scan = get_or_404(db, ScanRun, body.scan_run_id)
    if scan.project_id != project_id:
        raise HTTPException(404, "ScanRun not found")
    if scan.status != "completed":
        raise HTTPException(409, "Discovery must complete before generating tests")
    return api_testing.generate(db, scan)
