# tests/test_errors.py
from ent_exporter.errors import EntExporterError, AuthError, CaptchaLockedError, MediaResolveError

def test_error_hierarchy():
    assert issubclass(AuthError, EntExporterError)
    assert issubclass(CaptchaLockedError, AuthError)
    assert issubclass(MediaResolveError, EntExporterError)
