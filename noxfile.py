"""Nox sessions for texsmith."""

from pathlib import Path

import nox


PYPROJECT = nox.project.load_toml("pyproject.toml")
# Drive the matrix from pyproject metadata so versions stay in sync.
PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT, max_version="3.14")
MKDOCS_PLUGIN_PATH = Path(__file__).parent / "packages" / "mkdocs_texsmith"
nox.options.default_venv_backend = "uv"


def _install_test_deps(session: nox.Session) -> None:
    deps = list(nox.project.dependency_groups(PYPROJECT, "dev"))
    deps = [dep for dep in deps if not dep.lower().startswith("mkdocs-texsmith")]
    deps.insert(0, str(MKDOCS_PLUGIN_PATH))
    session.install(".", *deps)


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run pytest across all supported Python versions."""
    _install_test_deps(session)
    session.run("pytest", *session.posargs)


@nox.session(python="3.14")
def coverage(session: nox.Session) -> None:
    """Run tests with coverage reporting once (py3.14)."""
    _install_test_deps(session)
    session.run(
        "pytest",
        "--cov=texsmith",
        "--cov-report=term-missing",
        *session.posargs,
    )
