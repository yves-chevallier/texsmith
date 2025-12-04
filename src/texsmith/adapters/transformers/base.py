"""Primitives used by asset converter strategies."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Any, Protocol

from texsmith.core.exceptions import TransformerExecutionError


class ConverterStrategy(Protocol):
    """Protocol implemented by concrete converter strategies."""

    def __call__(self, source: Path | str, *, output_dir: Path, **options: Any) -> Any: ...


def exponential_backoff(
    base_delay: float = 0.5, factor: float = 2.0, max_delay: float = 5.0
) -> Callable[[int], float]:
    """Return a simple exponential backoff policy."""

    def policy(attempt: int) -> float:
        delay = base_delay * (factor ** (attempt - 1))
        return min(delay, max_delay)

    return policy


class CachedConversionStrategy:
    """Base class that adds caching and retry/backoff policies."""

    suffix: str = ".pdf"

    def __init__(
        self,
        namespace: str,
        *,
        max_attempts: int = 3,
        backoff: Callable[[int], float] | None = None,
    ) -> None:
        self.namespace = namespace
        self.max_attempts = max_attempts
        self.backoff = backoff or exponential_backoff()

    def __call__(self, source: Path | str, *, output_dir: Path, **options: Any) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cacheable_options = {key: value for key, value in options.items() if key != "emitter"}

        cache_key = self._make_cache_key(source, cacheable_options)
        target = self._resolve_target_path(output_dir, cache_key, source, options)

        if target.exists() and not options.get("force", False):
            return target

        cache_dir = output_dir / ".cache" / self.namespace
        cache_dir.mkdir(parents=True, exist_ok=True)

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._perform_conversion(
                    source, target=target, cache_dir=cache_dir, **options
                )
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                should_retry = attempt < self.max_attempts and not isinstance(
                    exc, TransformerExecutionError
                )
                if not should_retry:
                    raise
                delay = self.backoff(attempt)
                if delay > 0:
                    time.sleep(delay)

        if isinstance(last_error, TransformerExecutionError):
            raise last_error

        message = f"Conversion failed for '{self.namespace}' after {self.max_attempts} attempts"
        raise TransformerExecutionError(message) from last_error

    # --------------------------------------------------------------------- helpers

    def _perform_conversion(
        self,
        source: Path | str,
        *,
        target: Path,
        cache_dir: Path,
        **options: Any,
    ) -> Path:
        """Sub-classes must implement actual conversion logic."""
        raise NotImplementedError

    def _resolve_target_path(
        self,
        output_dir: Path,
        cache_key: str,
        source: Path | str,
        options: dict[str, Any],
    ) -> Path:
        suffix = self.output_suffix(source=source, options=options)
        return output_dir / f"{cache_key}{suffix}"

    def output_suffix(self, source: Any, options: dict[str, Any]) -> str:
        """Allow subclasses to customise the output suffix."""
        return self.suffix

    def _make_cache_key(self, source: Path | str, options: dict[str, Any]) -> str:
        digest = sha256()
        digest.update(self._serialise_source(source))
        digest.update(self._serialise_options(options))
        return digest.hexdigest()

    def _serialise_source(self, source: Path | str) -> bytes:
        if isinstance(source, Path):
            if source.exists():
                return source.read_bytes()
            return str(source.resolve()).encode("utf-8")
        return source.encode("utf-8")

    def _serialise_options(self, options: dict[str, Any]) -> bytes:
        normalised = {key: self._normalise_option(value) for key, value in options.items()}
        return json.dumps(normalised, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _normalise_option(self, value: Any) -> Any:
        match value:
            case Path():
                return value.as_posix()
            case list() | tuple():
                return [self._normalise_option(item) for item in value]
            case dict():
                return {str(k): self._normalise_option(v) for k, v in value.items()}
            case _:
                return value
