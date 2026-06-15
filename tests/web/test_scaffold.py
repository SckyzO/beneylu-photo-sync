def test_web_package_and_deps_importable():
    import ent_exporter.web  # noqa: F401
    import fastapi  # noqa: F401
    import jinja2  # noqa: F401
    from fastapi.testclient import TestClient  # noqa: F401
