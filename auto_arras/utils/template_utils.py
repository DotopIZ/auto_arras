"""Utils for modifying and reading template."""

from typer import FileTextWrite


def template_to_str(template: list[str]):
    """Turns template into string."""

    return '\n'.join(template)


def save_template(template: list[str], save_path: FileTextWrite):
    """Saves template as file."""

    text_template = template_to_str(template)

    save_path.write(text_template)
    return text_template
