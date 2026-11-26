"""Local preview: embedded Postgres + API + built frontend on one port (the container does the same with a real Postgres)."""
import os
import sys
from pathlib import Path

import pgembed
import uvicorn

here = Path(__file__).parent
pg = pgembed.get_server(str(here.parent / ".pgdata"), cleanup_mode=None)
os.environ["DATABASE_URL"] = pg.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
os.environ.setdefault("STATIC_DIR", str(here.parent / "frontend" / "out"))
sys.path.insert(0, str(here))
uvicorn.run("main:app", host="127.0.0.1", port=int(os.environ.get("PORT", 8765)))
