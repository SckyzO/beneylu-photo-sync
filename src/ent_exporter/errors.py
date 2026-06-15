# src/ent_exporter/errors.py
class EntExporterError(Exception):
    """Base error."""

class AuthError(EntExporterError):
    """Login or token refresh failed."""

class CaptchaLockedError(AuthError):
    """Account temporarily locked (X-Bns-Captcha)."""

class MediaResolveError(EntExporterError):
    """Could not resolve a media's signed download URL."""
