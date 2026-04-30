from __future__ import annotations
import pathlib
from typing import Literal
from jinja2 import Environment, FileSystemLoader


def model_format_style(model: str) -> Literal["xml", "markdown"]:
    """Return 'xml' for Anthropic/Claude models, 'markdown' for all others."""
    if model.startswith("anthropic:"):
        return "xml"
    return "markdown"


def render_prompt(template_path: pathlib.Path, **kwargs) -> str:
    """Render a Jinja2 template with given keyword arguments."""
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(template_path.name).render(**kwargs)
