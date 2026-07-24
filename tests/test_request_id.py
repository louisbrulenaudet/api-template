from fastapi.testclient import TestClient

from app.middlewares.request_id import get_request_id


def test_request_id_header_is_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id
    assert len(request_id) >= 8


def test_request_id_echoes_inbound_value(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers.get("x-request-id") == "trace-abc-123"


def test_request_id_is_unique_per_request(client: TestClient) -> None:
    first = client.get("/api/v1/health").headers["x-request-id"]
    second = client.get("/api/v1/health").headers["x-request-id"]
    assert first != second


def test_error_response_carries_request_id(client: TestClient) -> None:
    response = client.get("/raise-core-error", headers={"X-Request-ID": "err-trace-1"})
    assert response.status_code == 400
    assert response.headers.get("x-request-id") == "err-trace-1"
    assert response.json()["request_id"] == "err-trace-1"


def test_get_request_id_is_empty_outside_request() -> None:
    assert get_request_id() == ""
