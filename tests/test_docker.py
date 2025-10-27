from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from texsmith.adapters import docker as docker_mod


class _StubResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_container_builds_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorded: dict[str, list[str]] = {}

    monkeypatch.setattr(docker_mod.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(docker_mod.os, "getuid", lambda: 501, raising=False)
    monkeypatch.setattr(docker_mod.os, "getgid", lambda: 20, raising=False)

    def fake_run(cmd: list[str], **kwargs: Any) -> _StubResult:
        recorded["command"] = cmd
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        return _StubResult()

    monkeypatch.setattr(docker_mod.subprocess, "run", fake_run)
    docker_mod._default_runner.reset()

    docker_mod.run_container(
        "example/image",
        args=["--demo"],
        mounts=[docker_mod.VolumeMount(tmp_path, "/data")],
        environment={"HOME": "/sandbox"},
        workdir="/data",
        limits=docker_mod.DockerLimits(cpus=1.5, memory="256m", pids_limit=128),
    )

    expected_mount = f"type=bind,src={tmp_path.resolve()},dst=/data"
    assert recorded["command"] == [
        "/usr/bin/docker",
        "run",
        "--rm",
        "--user",
        "501:20",
        "-e",
        "HOME=/sandbox",
        "--workdir",
        "/data",
        "--mount",
        expected_mount,
        "--cpus",
        "1.5",
        "--memory",
        "256m",
        "--pids-limit",
        "128",
        "example/image",
        "--demo",
    ]


def test_run_container_can_disable_host_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: dict[str, list[str]] = {}

    monkeypatch.setattr(docker_mod.shutil, "which", lambda _: "/usr/bin/docker")

    def fake_run(cmd: list[str], **kwargs: Any) -> _StubResult:
        recorded["command"] = cmd
        return _StubResult()

    monkeypatch.setattr(docker_mod.subprocess, "run", fake_run)
    docker_mod._default_runner.reset()

    docker_mod.run_container(
        "example/image",
        mounts=[docker_mod.VolumeMount(tmp_path, "/data")],
        workdir="/data",
        use_host_user=False,
    )

    assert "--user" not in recorded["command"]


def test_run_container_missing_mount(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(docker_mod.shutil, "which", lambda _: "/usr/bin/docker")
    docker_mod._default_runner.reset()
    missing = tmp_path / "missing"

    with pytest.raises(docker_mod.TransformerExecutionError):
        docker_mod.run_container(
            "example/image",
            mounts=[docker_mod.VolumeMount(missing, "/data")],
        )


def test_is_docker_available_handles_lookup_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_: str) -> None:
        raise AssertionError("no docker")

    monkeypatch.setattr(docker_mod.shutil, "which", fail)
    docker_mod._default_runner.reset()
    assert docker_mod.is_docker_available() is False
