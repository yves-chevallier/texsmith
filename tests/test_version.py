from typer.testing import CliRunner

import texsmith
from texsmith.ui.cli import app


def test_get_version_matches_public_api() -> None:
    assert texsmith.get_version() == texsmith.__version__
    assert isinstance(texsmith.__version__, str)


def test_cli_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.stdout
    assert result.stdout.strip() == texsmith.get_version()
