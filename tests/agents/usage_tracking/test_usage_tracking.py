import asyncio

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agents._base.config import UsageTrackingAgentConfig
from agents._base.types import Fact, Quote
from agents.extraction.agent import ExtractionResult
from agents.usage_tracking.agent import _UsageOutput, run_usage_tracking_agent
from agents.writer.agent import ArticleHtml

_ARTICLE = ArticleHtml(html="<p>Fact one happened. Quote: hello world.</p>")
_EXTRACTION = ExtractionResult(
    facts=[
        Fact(text="Fact one happened", context="ctx", source_url="https://a.com", source_title="A")
    ],
    quotes=[Quote(text="hello world", speaker="Bob", context="ctx", source_url="https://a.com")],
    keywords=["kw"],
)
_CONFIG = UsageTrackingAgentConfig()


def test_returns_used_facts_and_quotes():
    mock_agent = Agent(
        TestModel(
            custom_output_args={"used_facts": ["Fact one happened"], "used_quotes": ["hello world"]}
        ),
        output_type=_UsageOutput,
    )
    used_facts, used_quotes = asyncio.run(
        run_usage_tracking_agent(
            _ARTICLE, extraction_result=_EXTRACTION, config=_CONFIG, _agent=mock_agent
        )
    )
    assert used_facts == ["Fact one happened"]
    assert used_quotes == ["hello world"]


def test_returns_empty_on_empty_extraction():
    empty_extraction = ExtractionResult(facts=[], quotes=[], keywords=[])
    used_facts, used_quotes = asyncio.run(
        run_usage_tracking_agent(_ARTICLE, extraction_result=empty_extraction, config=_CONFIG)
    )
    assert used_facts == []
    assert used_quotes == []
