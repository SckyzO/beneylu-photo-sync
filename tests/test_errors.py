# tests/test_errors.py
from beneylu_photo_sync.core.errors import BeneyluError, AuthError, CaptchaLockedError, MediaResolveError

def test_error_hierarchy():
    assert issubclass(AuthError, BeneyluError)
    assert issubclass(CaptchaLockedError, AuthError)
    assert issubclass(MediaResolveError, BeneyluError)
