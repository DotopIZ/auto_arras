"""Types and utils for typer."""

from pathlib import Path

from typing_extensions import Annotated
from typer import Argument


FileArgument = Argument(
    exists=True,
    file_okay=True,
    dir_okay=False,
    writable=False,
    readable=True,
    resolve_path=True
)

DirArgument = Argument(
    exists=True,
    file_okay=False,
    dir_okay=True,
    writable=False,
    readable=False,
    resolve_path=True
)


FilePathType = Annotated[
    Path,
    FileArgument
]

DirPathType = Annotated[
    Path,
    DirArgument
]
