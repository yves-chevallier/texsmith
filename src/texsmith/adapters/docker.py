"""Abstractions for invoking Docker containers safely."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess

from texsmith.core.exceptions import TransformerExecutionError


@dataclass(slots=True)
class VolumeMount:
    """Bind mount configuration."""

    source: Path | str
    target: str
    read_only: bool = False


@dataclass(slots=True)
class DockerLimits:
    """Runtime constraints for Docker containers."""

    cpus: float | int | None = None
    memory: str | None = None
    pids_limit: int | None = None


@dataclass(slots=True)
class DockerRunRequest:
    """Full request payload for a Docker execution."""

    image: str
    args: Sequence[str] = field(default_factory=tuple)
    mounts: Sequence[VolumeMount] = field(default_factory=tuple)
    environment: Mapping[str, str] = field(default_factory=dict)
    workdir: str | None = None
    user: str | None = None
    use_host_user: bool = True
    remove: bool = True
    limits: DockerLimits | None = None
    network: str | None = None
    extra_args: Sequence[str] = field(default_factory=tuple)


class DockerRunner:
    """Utility class encapsulating Docker invocations."""

    def __init__(self, executable: str | None = None) -> None:
        self._explicit_executable = executable
        self._cached_executable: str | None = None

    def is_available(self) -> bool:
        """Return True when Docker can be located."""
        try:
            return self._resolve_executable(optional=True) is not None
        except TransformerExecutionError:
            return False

    def reset(self) -> None:
        """Clear cached executable lookup results."""
        self._cached_executable = None

    def run(
        self,
        request: DockerRunRequest,
        *,
        capture_output: bool = True,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Execute Docker with the supplied request."""
        command = self._build_run_command(request)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=capture_output,
                text=text,
            )
        except FileNotFoundError as exc:
            self._cached_executable = None
            raise TransformerExecutionError("Docker executable could not be located.") from exc
        except OSError as exc:
            raise TransformerExecutionError(f"Failed to invoke Docker: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout
            message = f"Docker image '{request.image}' failed with exit code {result.returncode}"
            if detail:
                message = f"{message}: {detail}"
            raise TransformerExecutionError(message)

        return result

    def _build_run_command(self, request: DockerRunRequest) -> list[str]:
        executable = self._resolve_executable(optional=False)
        assert executable is not None
        command: list[str] = [executable, "run"]

        if request.remove:
            command.append("--rm")

        if request.extra_args:
            command.extend(request.extra_args)

        user = request.user or (self._resolve_host_user() if request.use_host_user else None)
        if user:
            command.extend(["--user", user])

        if request.environment:
            for key in sorted(request.environment):
                value = request.environment[key]
                command.extend(["-e", f"{key}={value}"])

        if request.workdir:
            command.extend(["--workdir", request.workdir])

        if request.network:
            command.extend(["--network", request.network])

        command.extend(self._build_mounts(request.mounts))
        command.extend(self._build_limits(request.limits))

        command.append(request.image)
        command.extend(request.args)
        return command

    def _build_mounts(self, mounts: Sequence[VolumeMount]) -> list[str]:
        flags: list[str] = []
        for mount in mounts:
            host = Path(mount.source).expanduser()
            if not host.exists():
                raise TransformerExecutionError(f"Docker mount source '{host}' does not exist.")
            try:
                resolved = host.resolve(strict=True)
            except (OSError, RuntimeError):
                resolved = host.absolute()

            parts = [
                "type=bind",
                f"src={resolved}",
                f"dst={mount.target}",
            ]

            if mount.read_only:
                parts.append("readonly")

            flags.extend(["--mount", ",".join(parts)])
        return flags

    def _build_limits(self, limits: DockerLimits | None) -> list[str]:
        if limits is None:
            return []

        flags: list[str] = []
        if limits.cpus is not None:
            flags.extend(["--cpus", str(limits.cpus)])
        if limits.memory:
            flags.extend(["--memory", str(limits.memory)])
        if limits.pids_limit is not None:
            flags.extend(["--pids-limit", str(limits.pids_limit)])
        return flags

    def _resolve_executable(self, *, optional: bool) -> str | None:
        if self._explicit_executable:
            return self._explicit_executable

        if self._cached_executable:
            return self._cached_executable

        try:
            executable = shutil.which("docker")
        except (AssertionError, OSError, ValueError):
            executable = None

        if executable:
            self._cached_executable = executable
            return executable

        if optional:
            return None

        raise TransformerExecutionError("Docker is required but was not found on PATH.")

    def _resolve_host_user(self) -> str | None:
        getuid = getattr(os, "getuid", None)
        getgid = getattr(os, "getgid", None)

        if callable(getuid) and callable(getgid):
            try:
                uid = getuid()
                gid = getgid()
            except OSError:
                return None
            return f"{uid}:{gid}"

        return None


_default_runner = DockerRunner()


def is_docker_available() -> bool:
    """Check if Docker can be executed."""
    return _default_runner.is_available()


def run_container(
    image: str,
    args: Sequence[str] = (),
    *,
    mounts: Sequence[VolumeMount] = (),
    environment: Mapping[str, str] | None = None,
    workdir: str | None = None,
    user: str | None = None,
    use_host_user: bool = True,
    limits: DockerLimits | None = None,
    network: str | None = None,
    remove: bool = True,
    extra_args: Sequence[str] = (),
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute Docker using the shared runner."""
    request = DockerRunRequest(
        image=image,
        args=tuple(args),
        mounts=tuple(mounts),
        environment=environment or {},
        workdir=workdir,
        user=user,
        use_host_user=use_host_user,
        remove=remove,
        limits=limits,
        network=network,
        extra_args=tuple(extra_args),
    )
    return _default_runner.run(
        request,
        capture_output=capture_output,
        text=text,
    )


__all__ = [
    "DockerLimits",
    "DockerRunRequest",
    "DockerRunner",
    "VolumeMount",
    "is_docker_available",
    "run_container",
]
