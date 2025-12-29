"""HTTP helpers with cross-platform TLS guidance."""

from __future__ import annotations

from collections.abc import Mapping
import ssl
from typing import Any
import urllib.error
import urllib.request


class TLSCertificateError(RuntimeError):
    """Raised when TLS certificate verification fails during downloads."""


def _tls_help(url: str) -> str:
    return (
        "TLS certificate verification failed while downloading "
        f"'{url}'. On macOS run the Python 'Install Certificates.command' "
        "(from the python.org installer). On Windows run 'py -m pip install --upgrade certifi'. "
        "On Linux install your 'ca-certificates' package (apt/yum/apk). "
        "Also check system date/time and any proxy or corporate SSL inspection."
    )


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore[import]
    except Exception:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _is_cert_error(error: urllib.error.URLError) -> bool:
    reason = getattr(error, "reason", None)
    return isinstance(reason, ssl.SSLCertVerificationError)


def open_url(
    url: str | urllib.request.Request,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> Any:
    """Open a URL with a default SSL context and cert guidance on failure."""
    request = url
    if isinstance(url, str):
        request = urllib.request.Request(url, headers=dict(headers or {}))
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())
    except urllib.error.URLError as exc:
        if _is_cert_error(exc):
            raise TLSCertificateError(_tls_help(str(getattr(request, "full_url", url)))) from exc
        raise


__all__ = ["TLSCertificateError", "open_url"]
