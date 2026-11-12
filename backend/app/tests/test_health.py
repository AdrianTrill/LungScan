"""Unit tests for the health and model endpoints."""


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_model_endpoint_names_the_classes(client):
    body = client.get("/api/model").json()
    assert body["source"] == "fake/model@0000000"
    assert body["available"] is False
    assert [label["id"] for label in body["labels"]] == [
        "adenocarcinoma",
        "large_cell_carcinoma",
        "normal",
        "squamous_cell_carcinoma",
    ]
