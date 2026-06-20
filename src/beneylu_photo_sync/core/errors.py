# src/beneylu_photo_sync/core/errors.py
class BeneyluError(Exception):
    """Base error."""

class AuthError(BeneyluError):
    """Login or token refresh failed."""

class CaptchaLockedError(AuthError):
    """Account temporarily locked (X-Bns-Captcha)."""

class MediaResolveError(BeneyluError):
    """Could not resolve a media's signed download URL."""
