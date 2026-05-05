from __future__ import annotations

import pathlib
from datetime import UTC, datetime
from typing import Literal

from jinja2 import Environment, FileSystemLoader


def model_format_style(model: str) -> Literal["xml", "markdown"]:
    """Return 'xml' for Anthropic/Claude models, 'markdown' for all others."""
    if model.startswith("anthropic:"):
        return "xml"
    return "markdown"


def render_prompt(template_path: pathlib.Path, **kwargs) -> str:
    """Render a Jinja2 template with given keyword arguments.

    Every rendered prompt gets a single 'Today's date: YYYY-MM-DD' line
    prepended. LLMs need this anchor for tense decisions, recency calls
    ('news from last week'), age calculations, and detecting their own
    training-data drift — without it Gemini routinely writes about the
    cutoff month as if it were 'now'. Done at the renderer level so adding
    a new agent doesn't risk forgetting it.
    """
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    body = env.get_template(template_path.name).render(**kwargs)
    today = datetime.now(UTC).date().isoformat()
    return f"Today's date: {today}\n\n{body}"
