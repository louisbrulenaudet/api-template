from app.enums.error_codes import ErrorCodes
from app.exceptions.authentication_error import AuthenticationError
from app.exceptions.client_initialization_error import ClientInitializationError
from app.exceptions.core_exception import CoreError


def test_core_error_str():
    err = CoreError("msg", ErrorCodes.VALIDATION_ERROR, {"foo": "bar"})
    rendered = str(err)

    assert "CoreError" in rendered
    assert "msg" in rendered
    assert "VALIDATION_ERROR" in rendered
    assert "{'foo': 'bar'}" in rendered


def test_core_error_str_without_details():
    err = CoreError("msg", ErrorCodes.VALIDATION_ERROR)

    assert "Details" not in str(err)


def test_core_error_attributes():
    # `to_dict()` was removed deliberately: `app.dtos.error_response.ErrorResponse` is the single
    # owner of the client-facing shape. Assert on the exception's own attributes instead.
    err = CoreError("msg", ErrorCodes.VALIDATION_ERROR, {"foo": "bar"})

    assert err.message == "msg"
    assert err.code == ErrorCodes.VALIDATION_ERROR
    assert err.details == {"foo": "bar"}
    assert err.http_status_code == 400


def test_client_initialization_error():
    err = ClientInitializationError("fail")

    assert isinstance(err, CoreError)
    assert err.message == "The client initialization failed."
    assert err.code == ErrorCodes.CLIENT_INITIALIZATION_ERROR
    assert err.http_status_code == 500
    assert isinstance(err.details, str)
    assert "fail" in err.details


def test_authentication_error():
    err = AuthenticationError("Missing or invalid API key.")

    assert isinstance(err, CoreError)
    assert err.code == ErrorCodes.AUTHENTICATION_ERROR
    assert err.http_status_code == 401
