import os

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_template(template_name: str, context: dict) -> str:
    template_dir = os.path.join(
        os.path.dirname(__file__), "..", "core", "dependencies", "email", "templates"
    )
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)
    return template.render(**context)
