# tests/test_smoke.py
def test_package_imports():
    import ent_exporter
    assert ent_exporter.__version__ == "0.1.0"
