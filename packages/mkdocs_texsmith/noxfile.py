"""Nox sessions for the mkdocs-texsmith plugin."""

from pathlib import Path

import nox


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent  # texsmith repo root
PYPROJECT = nox.project.load_toml("pyproject.toml")
PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT, max_version="3.13")


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run pytest for the plugin across supported Python versions."""
    deps = list(nox.project.dependency_groups(PYPROJECT, "dev"))
    session.install(str(REPO_ROOT), ".")  # Install core texsmith and the plugin itself
    session.install(*deps)
    session.run("pytest", *session.posargs)
