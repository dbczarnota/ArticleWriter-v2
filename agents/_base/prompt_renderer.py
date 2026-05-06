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


_WEEKDAY = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def render_prompt(template_path: pathlib.Path, **kwargs) -> str:
    """Render a Jinja2 template with given keyword arguments.

    Every rendered prompt gets a single date-anchor line prepended:
    'Today's date: YYYY-MM-DD (Weekday)'. LLMs need this for tense
    decisions, recency calls ('news from last week'), age calculations,
    and detecting their own training-data drift — without it Gemini
    routinely writes about the cutoff month as if it were 'now'. The
    weekday is added because models occasionally hallucinate the day
    name when asked ('the press conference was held on Tuesday' when
    'today' was actually Friday). Done at the renderer level so adding
    a new agent doesn't risk forgetting it.
    """
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    body = env.get_template(template_path.name).render(**kwargs)
    now = datetime.now(UTC)
    today = now.date().isoformat()
    weekday = _WEEKDAY[now.weekday()]
    return f"Today's date: {today} ({weekday})\n\n{body}"
