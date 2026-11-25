"""Entry point for the auto_arras CLI."""

import typer

from auto_arras import generate_template
from auto_arras import print_template


app = typer.Typer(
    name="auto-arras",
    help="Automate arras.io sandbox: generate macros from images and paste them.",
    no_args_is_help=True,
)

app.add_typer(print_template.app, name="paste")
app.add_typer(generate_template.app, name="generate")

def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
