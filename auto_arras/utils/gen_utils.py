"""
from . import template_aliases

def alias_template(template: list[str]):
    new_template = []
    changed = 0
    for line in template:
        line = line.removesuffix('\n')
        tokens = line.split()
        cmd = tokens[0]
        args = tokens[1:]
        try:
            alias = getattr(template_aliases, cmd)(args)
            changed = 1
        except AttributeError:
            alias = [line]
        new_template.extend(alias)
    return new_template, changed

def compile_template(template: list[str]):
    changed = 1
    while changed:
        template, changed = alias_template(template)
    return template"""

def compile_template(template):
    # Do fucking nothing
    return list(template)