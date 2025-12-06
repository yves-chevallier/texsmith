"""Helpers for resolving DOIs to BibTeX payloads."""

from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:  # pragma: no cover - typing only
    from requests import Session as RequestsSession  # type: ignore[import]
else:
    RequestsSession = Any  # type: ignore[misc]

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]

from texsmith.core.user_dir import get_user_dir


class DoiLookupError(Exception):
    """Raised when resolving a DOI to a BibTeX payload fails."""


def normalise_doi(value: str) -> str:
    """Return a canonical representation for DOI strings."""
    if not isinstance(value, str):
        raise DoiLookupError("DOI must be provided as a string.")
    candidate = value.strip()
    if not candidate:
        raise DoiLookupError("DOI value is empty.")

    lowered = candidate.lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if lowered.startswith(prefix):
            candidate = candidate[len(prefix) :]
            break

    candidate = candidate.strip()
    if candidate.lower().startswith("doi:"):
        candidate = candidate.split(":", 1)[1]

    candidate = candidate.strip().strip("/")
    if not candidate:
        raise DoiLookupError("DOI value is empty.")
    return candidate


class DoiBibliographyFetcher:
    """Retrieve BibTeX entries for DOIs using content negotiation fallbacks."""

    _DEFAULT_USER_AGENT = "texsmith-bibliography-fetcher"
    _BIBTEX_ACCEPT = "application/x-bibtex"
    _CACHE_NAMESPACE = "bibliography"

    def __init__(
        self,
        *,
        session: RequestsSession | None = None,
        timeout: float = 10.0,
        user_agent: str | None = None,
        cache: MutableMapping[str, str] | None = None,
        cache_dir: Path | None = None,
        enable_cache: bool = True,
    ) -> None:
        self._session_lock = Lock()
        self._session: RequestsSession | None = session
        self._timeout = timeout
        self._user_agent = user_agent or self._DEFAULT_USER_AGENT
        self._cache: MutableMapping[str, str] = cache or {}
        self._enable_cache = enable_cache
        resolved_cache_dir = self._resolve_cache_dir(cache_dir) if enable_cache else None
        if session is not None and cache_dir is None:
            resolved_cache_dir = None
        self._cache_dir = resolved_cache_dir if enable_cache else None

        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, value: str) -> str:
        """Return the BibTeX payload for a DOI, trying multiple providers."""
        if requests is None:
            msg = (
                "Python 'requests' dependency is required to resolve DOIs. "
                "Install it via 'pip install requests'."
            )
            raise DoiLookupError(msg)

        doi = self._normalise(value)
        cached = self._read_cache(doi)
        if cached is not None:
            return cached

        attempts: list[str] = []
        client = self._ensure_session()
        for url, headers in self._candidate_requests(doi):
            try:
                response = client.get(url, headers=headers, timeout=self._timeout)
            except requests.RequestException as exc:
                attempts.append(f"{url}: {exc}")
                continue
            if response.status_code >= 400:
                attempts.append(f"{url}: HTTP {response.status_code}")
                continue
            content = response.text.strip()
            if content:
                self._write_cache(doi, content)
                return content
            attempts.append(f"{url}: empty response")
        detail = "; ".join(attempts) if attempts else "no responses"
        raise DoiLookupError(f"Unable to resolve DOI '{doi}': {detail}")

    def _normalise(self, value: str) -> str:
        return normalise_doi(value)

    def _candidate_requests(self, doi: str) -> Iterable[tuple[str, dict[str, str]]]:
        base_headers = {"User-Agent": self._user_agent}

        yield (
            f"https://doi.org/{doi}",
            {**base_headers, "Accept": self._BIBTEX_ACCEPT},
        )
        yield (
            f"https://dx.doi.org/{doi}",
            {**base_headers, "Accept": self._BIBTEX_ACCEPT},
        )
        yield (
            f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex",
            dict(base_headers),
        )

    # ------------------------------------------------------------------ caching

    def _read_cache(self, doi: str) -> str | None:
        if not self._enable_cache:
            return None
        if doi in self._cache:
            return self._cache[doi]
        path = self._disk_cache_path(doi)
        if path is None or not path.exists():
            return None
        try:
            payload = path.read_text(encoding="utf-8")
        except OSError:
            return None
        self._cache[doi] = payload
        return payload

    def _write_cache(self, doi: str, payload: str) -> None:
        if not self._enable_cache:
            return
        self._cache[doi] = payload
        path = self._disk_cache_path(doi)
        if path is None:
            return
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError:
            # Disk caches should never break the primary workflow.
            return

    def _disk_cache_path(self, doi: str) -> Path | None:
        if self._cache_dir is None:
            return None
        digest = sha256(doi.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}.bib"

    def _resolve_cache_dir(self, override: Path | None) -> Path | None:
        if override is not None:
            return override

        try:
            return get_user_dir().cache_dir(self._CACHE_NAMESPACE)
        except OSError:
            return None

    # ------------------------------------------------------------------ requests

    def _ensure_session(self) -> RequestsSession:
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                self._session = requests.Session()
            return self._session
