# tests/agents/test_prompt_renderer.py
from agents._base.prompt_renderer import model_format_style, render_prompt


def test_anthropic_model_returns_xml():
    assert model_format_style("anthropic:claude-3-5-sonnet") == "xml"


def test_google_model_returns_markdown():
    assert model_format_style("google-gla:gemini-2.5-flash") == "markdown"


def test_openai_model_returns_markdown():
    assert model_format_style("openai:gpt-4o") == "markdown"


def test_groq_model_returns_markdown():
    assert model_format_style("groq:llama-3.3-70b") == "markdown"


def test_render_prompt_interpolates_variables(tmp_path):
    template = tmp_path / "test.j2"
    template.write_text("Hello {{ name }}! Queries: {{ num }}")
    result = render_prompt(template, name="World", num=3)
    assert "Hello World! Queries: 3" in result


def test_render_prompt_prepends_current_date(tmp_path):
    """Every rendered prompt starts with today's date so LLMs have a temporal
    anchor for tense, recency, and age calculations."""
    from datetime import UTC, datetime

    template = tmp_path / "test.j2"
    template.write_text("body content")
    result = render_prompt(template)
    today = datetime.now(UTC).date().isoformat()
    assert result.startswith(f"Today's date: {today}")
    assert "body content" in result


def test_render_prompt_prepends_weekday(tmp_path):
    """Date anchor includes the weekday name so LLMs don't hallucinate a
    different day of the week when describing 'today'."""
    from datetime import UTC, datetime

    weekdays = {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }
    template = tmp_path / "test.j2"
    template.write_text("x")
    result = render_prompt(template)
    today = datetime.now(UTC).date()
    expected_weekday = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )[today.weekday()]
    assert f"({expected_weekday})" in result.split("\n", 1)[0]
    assert expected_weekday in weekdays


def test_render_prompt_xml_branch(tmp_path):
    template = tmp_path / "test.j2"
    template.write_text(
        "{% if format_style == 'xml' %}<task>{{ content }}</task>"
        "{% else %}## TASK\n{{ content }}{% endif %}"
    )
    xml_result = render_prompt(template, format_style="xml", content="do this")
    md_result = render_prompt(template, format_style="markdown", content="do this")
    assert "<task>do this</task>" in xml_result
    assert "## TASK" in md_result
    assert "<task>" not in md_result
