from fastapi import FastAPI

from app import get_app


def test_get_app_import_and_call() -> None:
    app_instance = get_app()
    # The returned object should be a FastAPI app
    assert isinstance(app_instance, FastAPI)
