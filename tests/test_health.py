import os

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def test_health_endpoint_running():
    # This requires the server to be running locally
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
