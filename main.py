"""Tool for automation arras.io sandbox."""

import typer

from auto_arras import generate_template
from auto_arras import print_template


app = typer.Typer(no_args_is_help=True)

app.add_typer(print_template.app)
app.add_typer(generate_template.app, name='generate')


@app.callback()
def main():
    """Tool for automation arras.io sandbox."""


if __name__ == "__main__":
    app()
