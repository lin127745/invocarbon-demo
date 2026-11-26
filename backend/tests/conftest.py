import os
import sys
import tempfile
from pathlib import Path

import pgembed
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_pg = pgembed.get_server(tempfile.mkdtemp(prefix="invocarbon-pg-"), cleanup_mode="stop")
os.environ["DATABASE_URL"] = _pg.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
os.environ.pop("GEMINI_API_KEY", None)  # tests exercise the keyword path; Gemini needs a real key


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)
