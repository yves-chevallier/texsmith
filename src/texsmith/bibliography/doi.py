"""Helpers for resolving DOIs to BibTeX payloads."""

from __future__ import annotations

from collections.abc import Iterable

import requests


class DoiLookupError(Exception):
    """Raised when resolving a DOI to a BibTeX payload fails."""


class DoiBibliographyFetcher:
    """Retrieve BibTeX entries for DOIs using content negotiation fallbacks."""

    _DEFAULT_USER_AGENT = "texsmith-bibliography-fetcher"
    _BIBTEX_ACCEPT = "application/x-bibtex"

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = 10.0,
        user_agent: str | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout
        self._user_agent = user_agent or self._DEFAULT_USER_AGENT

    def fetch(self, value: str) -> str:
        """Return the BibTeX payload for a DOI, trying multiple providers."""
        doi = self._normalise(value)
        attempts: list[str] = []
        for url, headers in self._candidate_requests(doi):
            try:
                response = self._session.get(url, headers=headers, timeout=self._timeout)
            except requests.RequestException as exc:
                attempts.append(f"{url}: {exc}")
                continue
            if response.status_code >= 400:
                attempts.append(f"{url}: HTTP {response.status_code}")
                continue
            content = response.text.strip()
            if content:
                return content
            attempts.append(f"{url}: empty response")
        detail = "; ".join(attempts) if attempts else "no responses"
        raise DoiLookupError(f"Unable to resolve DOI '{doi}': {detail}")

    def _normalise(self, value: str) -> str:
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

