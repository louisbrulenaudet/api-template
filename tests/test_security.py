import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.core.security import API_KEY_HEADER_NAME, require_api_key
from app.enums.error_codes import ErrorCodes
from app.main import create_app
from tests.conftest import TEST_API_KEY, build_settings


@pytest.fixture(scope="module")
def protected_client() -> TestClient:
    """A client whose app has one API-key-protected route."""
    app = create_app(build_settings())
    protected = APIRouter(dependencies=[Depends(require_api_key)])

    @protected.get("/private")
    async def private() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(protected)
    return TestClient(app)


def test_valid_key_is_accepted(protected_client: TestClient) -> None:
    response = protected_client.get("/private", headers={API_KEY_HEADER_NAME: TEST_API_KEY})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_missing_key_is_rejected(protected_client: TestClient) -> None:
    response = protected_client.get("/private")

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == ErrorCodes.AUTHENTICATION_ERROR
    # The uniform envelope, not FastAPI's `{"detail": ...}` from `auto_error=True`.
    assert body["error"] == "AuthenticationError"


def test_wrong_key_is_rejected(protected_client: TestClient) -> None:
    response = protected_client.get("/private", headers={API_KEY_HEADER_NAME: "wrong"})

    assert response.status_code == 401


def test_wrong_key_response_never_echoes_the_expected_secret(
    protected_client: TestClient,
) -> None:
    response = protected_client.get("/private", headers={API_KEY_HEADER_NAME: "wrong"})

    assert TEST_API_KEY not in response.text


def test_unset_server_key_fails_closed() -> None:
    """An unconfigured API key must deny every request, never allow all of them."""
    app = create_app(build_settings(api_key=""))
    protected = APIRouter(dependencies=[Depends(require_api_key)])

    @protected.get("/private")
    async def private() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(protected)

    with TestClient(app) as client:
        # Not even an empty header may satisfy an empty configured key.
        assert client.get("/private").status_code == 401
        assert client.get("/private", headers={API_KEY_HEADER_NAME: ""}).status_code == 401


def test_api_key_scheme_is_published_to_openapi(protected_client: TestClient) -> None:
    """Swagger UI needs the scheme to render an Authorize box, despite `auto_error=False`."""
    schema = protected_client.get("/openapi.json").json()

    assert "APIKeyHeader" in schema["components"]["securitySchemes"]


def test_health_endpoints_stay_unauthenticated(client: TestClient) -> None:
    """Probes must never require a credential, or Docker/K8s healthchecks break."""
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ping").status_code == 200


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


def test_hsts_absent_without_force_https(client: TestClient) -> None:
    """HSTS on a plain-HTTP origin is ignored by browsers and misleading to operators."""
    assert "strict-transport-security" not in client.get("/api/v1/health").headers


def test_hsts_present_with_force_https() -> None:
    app = create_app(build_settings(force_https=True))

    with TestClient(app) as client:
        # `follow_redirects=False`: the redirect response itself must carry the header, which is
        # what proves SecurityHeadersMiddleware sits outside HTTPSRedirectMiddleware.
        # A non-probe path, since probe paths are exempt from the redirect entirely.
        response = client.get("/definitely-not-a-route", follow_redirects=False)

    assert response.status_code == 307
    assert "max-age=63072000" in response.headers["strict-transport-security"]


def test_security_headers_apply_to_error_responses(client: TestClient) -> None:
    response = client.get("/definitely-not-a-route")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"


def test_disallowed_host_is_rejected() -> None:
    """`TrustedHostMiddleware` must reject a spoofed Host header."""
    app = create_app(build_settings(allowed_hosts=["app.example"]))

    with TestClient(app, base_url="http://app.example") as client:
        assert client.get("/definitely-not-a-route").status_code == 404
        assert (
            client.get("/definitely-not-a-route", headers={"Host": "evil.example"}).status_code
            == 400
        )


def test_host_validation_precedes_https_redirect() -> None:
    """A spoofed Host must not be reflected into a redirect `Location` (open redirect)."""
    app = create_app(build_settings(force_https=True, allowed_hosts=["app.example"]))

    with TestClient(app, base_url="http://app.example") as client:
        response = client.get(
            "/definitely-not-a-route",
            headers={"Host": "evil.example"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "evil.example" not in response.headers.get("location", "")


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/ping"])
def test_probe_reaches_the_app_under_an_unnameable_host(path: str) -> None:
    """A probe calling by IP must not be answered with `400 Invalid host header`.

    The Dockerfile `HEALTHCHECK` requests `http://127.0.0.1:8001/api/v1/health` and a kubelet probe uses the pod IP, neither of which a production `ALLOWED_HOSTS` list can name - production rejects the `*` that would have allowed them. Without the exemption the container is permanently unhealthy, which is how this was found: CI's image smoke test logged nothing but 400s.
    """
    app = create_app(build_settings(allowed_hosts=["app.example"]))

    with TestClient(app, base_url="http://app.example") as client:
        assert client.get(path, headers={"Host": "127.0.0.1:8001"}).status_code == 200


def test_probe_is_not_redirected_under_force_https() -> None:
    """The exemption must cover the redirect too, not only host validation.

    The probe speaks plain HTTP to a loopback port; a 307 to `https://…` is one it cannot follow, so exempting the host check alone would leave the healthcheck just as broken.
    """
    app = create_app(build_settings(force_https=True, allowed_hosts=["app.example"]))

    with TestClient(app, base_url="http://app.example") as client:
        response = client.get(
            "/api/v1/health",
            headers={"Host": "127.0.0.1:8001"},
            follow_redirects=False,
        )

    assert response.status_code == 200


def test_probe_exemption_does_not_leak_to_other_paths() -> None:
    """Only the probe paths are exempt; a spoofed Host must still be rejected elsewhere."""
    app = create_app(build_settings(allowed_hosts=["app.example"]))

    with TestClient(app, base_url="http://app.example") as client:
        # A path that merely starts like a probe must not inherit the exemption.
        assert client.get("/api/v1/health/sub", headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/api/v1/ping", headers={"Host": "evil.example"}).status_code == 200
