import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ["TESTING"] = "1"
from app.main import app
from app.database.database import SessionLocal, init_db
from app.database.database import Base, engine

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    from app.services.seed import seed_demo_data
    seed_demo_data()
    yield


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["milestone"] == 1


def test_list_sites():
    r = client.get("/api/sites")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_site_not_found():
    r = client.get("/api/sites/nonexistent")
    assert r.status_code == 404


def test_dashboard_endpoint():
    r = client.get("/api/sites/site_riverside_main/dashboard")
    assert r.status_code == 200
    assert "site_name" in r.json()


def test_demo_generate():
    r = client.post("/api/demo/generate")
    assert r.status_code == 200
    assert "risk_score" in r.json()
    assert "risk_level" in r.json()


def test_demo_scenario():
    r = client.get("/api/demo/scenario")
    assert r.status_code == 200
    assert "zones" in r.json()


def test_invalid_monitoring_event():
    r = client.post("/api/monitoring/analyze", json={"site_id": "unknown_site"})
    # Missing required fields -> 422 validation error
    assert r.status_code == 422


def test_risk_analysis():
    r = client.post("/api/sites/site_riverside_main/risk/analyze")
    assert r.status_code == 200


def test_risk_history():
    r = client.get("/api/sites/site_riverside_main/risk/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_hazards_empty():
    r = client.get("/api/sites/site_riverside_main/hazards")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
