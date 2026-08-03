import httpx2
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.middlewares.request_id import get_request_id, request_id_from


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


class TestInboundSanitisation:
    """An inbound correlation ID is untrusted input; it lands in logs and a response header."""

    def test_value_with_spaces_is_replaced(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "evil id with spaces"})

        assert response.headers["x-request-id"] != "evil id with spaces"

    def test_log_forging_payload_is_replaced(self, client: TestClient) -> None:
        forged = 'a" ; level=CRITICAL msg="pwned'
        response = client.get("/api/v1/health", headers={"X-Request-ID": forged})

        assert response.headers["x-request-id"] != forged

    def test_overlong_value_is_replaced(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-ID": "x" * 300})

        assert len(response.headers["x-request-id"]) == 32

    def test_value_at_the_length_limit_is_accepted(self, client: TestClient) -> None:
        allowed = "y" * 128
        response = client.get("/api/v1/health", headers={"X-Request-ID": allowed})

        assert response.headers["x-request-id"] == allowed

    def test_empty_value_is_replaced(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"X-Request-ID": ""})

        assert response.headers["x-request-id"]


async def test_async_client_fixture_reaches_routes(async_client: httpx2.AsyncClient) -> None:
    """The async ASGI fixture must work, including the lifespan it has to start itself."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


class TestRequestIdFrom:
    """`request_id_from` must degrade gracefully when the scope carries no usable value."""

    def _request(self, **scope: object) -> Request:
        return Request({"type": "http", "headers": [], "method": "GET", "path": "/", **scope})

    def test_falls_back_when_scope_has_no_state(self) -> None:
        assert request_id_from(self._request()) == ""

    def test_falls_back_when_state_lacks_the_key(self) -> None:
        assert request_id_from(self._request(state={})) == ""

    def test_falls_back_when_state_value_is_not_a_string(self) -> None:
        # The state bag is untyped `Any`, so the value is re-checked rather than trusted.
        assert request_id_from(self._request(state={"request_id": 1234})) == ""

    def test_reads_the_scope_value(self) -> None:
        request = self._request(state={"request_id": "scoped-id"})

        assert request_id_from(request) == "scoped-id"
