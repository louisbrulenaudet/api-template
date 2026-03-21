def test_get_app_import_and_call():
    from app import get_app

    app_instance = get_app()
    # The returned object should be a FastAPI app
    from fastapi import FastAPI

    assert isinstance(app_instance, FastAPI)
