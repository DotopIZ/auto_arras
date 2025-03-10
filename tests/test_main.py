"""A placeholder for tests."""

from typer.testing import CliRunner

from main import app


runner = CliRunner()


def test_app():
    """A placeholder for test."""

    result = runner.invoke(app, ['--help'])
    assert result.exit_code == 0
