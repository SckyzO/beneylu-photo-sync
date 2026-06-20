def test_web_package_and_deps_importable():
    import beneylu_photo_sync.web  # noqa: F401
    import fastapi  # noqa: F401
    import jinja2  # noqa: F401
    from fastapi.testclient import TestClient  # noqa: F401
