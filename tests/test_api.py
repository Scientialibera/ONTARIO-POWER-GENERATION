from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_optimizer_api_with_explicit_prices():
    response = client.post(
        "/api/battery/optimize",
        json={
            "prices": [10, 10, 20, 30, 80, 100],
            "power_mw": 25,
            "energy_mwh": 75,
            "round_trip_efficiency": 0.9,
            "initial_soc_pct": 50,
            "min_soc_pct": 10,
            "max_soc_pct": 90,
            "degradation_cost_per_mwh": 1
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "optimal"
    assert payload["net_value"] > 0
