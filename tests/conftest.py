import os
import sys
import asyncio
from pathlib import Path

# ------------------------------------------------------------
# Eerst env goed zetten, pas daarna app imports
# ------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DISABLE_BG"] = "1"

# Verwijder statische AWS keys, want app startup verbiedt die expliciet
for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
    os.environ.pop(key, None)

# Lege Basic-Auth credentials zodat load_dotenv() de echte waarden niet overschrijft
# en de test-client gewoon "" + "" kan sturen (BasicAuthMiddleware laadt deze vóór import).
os.environ.setdefault("SALES_BASIC_AUTH_USER", "")
os.environ.setdefault("SALES_BASIC_AUTH_PASS", "")

TEST_DB_PATH = ROOT / "tests" / "test_db.sqlite3"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"

# Forceer test database vóór app imports
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, get_db

# Zorg dat alle modellen geregistreerd zijn
from app import models  # noqa: F401


connect_args = {"check_same_thread": False}
engine = create_engine(TEST_DATABASE_URL, connect_args=connect_args)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _create_test_db():
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope="session")
def client():
    def _get_test_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer testtoken"}
