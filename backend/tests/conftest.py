import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

_tmp = tempfile.mkdtemp(prefix="dragonfly-")
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/test.db", CELERY_EAGER="1", ARTIFACT_DIR=f"{_tmp}/artifacts",
                  ANTHROPIC_API_KEY="")

from app import models  # noqa: F401  (registers tables)
from app.db import Base, engine

Base.metadata.create_all(engine)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def demo_url(demo):
    return demo.url


@pytest.fixture(scope="session")
def demo():
    """Run the demo target app in-process on a free port. `demo.module.FIXED = True` ships the fix."""
    import importlib.util

    import uvicorn

    # Loaded by path under another name: the demo's app.py must not shadow the backend `app` package.
    spec = importlib.util.spec_from_file_location("demo_app", Path(__file__).resolve().parents[2] / "demo-app" / "app.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(demo.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield SimpleNamespace(url=f"http://127.0.0.1:{port}/", module=demo)
    server.should_exit = True
