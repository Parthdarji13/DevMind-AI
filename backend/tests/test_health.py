"""
Tests for API root and health endpoints.
"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["health"] == "/api/health"


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["service"] == "DevMind AI RAG Backend"
    assert data["version"] == "1.2.0"
    assert "storage_ready" in data
    assert "limits" in data
    assert data["limits"]["max_zip_mb"] == 100
    assert data["limits"]["max_files"] == 3000
