"""Unit tests for `_merge_pre_injected` helper in pipeline runner."""

from agents._base.types import Fact, Quote
from agents.extraction.agent import ExtractionResult
from agents.pipeline.runner import _merge_pre_injected


def test_merge_none_returns_extracted_as_is():
    extracted = ExtractionResult(
        facts=[Fact(text="a", context="bio", source_urls=["http://x"])],
        quotes=[],
        keywords=["k1"],
    )
    assert _merge_pre_injected(extracted, None) is extracted


def test_merge_empty_pre_injected_returns_extracted_unchanged():
    extracted = ExtractionResult(
        facts=[Fact(text="a", context="bio", source_urls=["http://x"])],
        quotes=[],
        keywords=["k1"],
    )
    pre = ExtractionResult(facts=[], quotes=[], keywords=[])
    merged = _merge_pre_injected(extracted, pre)
    assert [f.text for f in merged.facts] == ["a"]
    assert merged.quotes == []
    assert merged.keywords == ["k1"]


def test_merge_prepends_pre_injected_facts():
    pre = ExtractionResult(
        facts=[Fact(text="primary", context="editor note", source_urls=["editor-provided"])],
        quotes=[],
        keywords=[],
    )
    extracted = ExtractionResult(
        facts=[Fact(text="secondary", context="bio", source_urls=["http://x"])],
        quotes=[],
        keywords=[],
    )
    merged = _merge_pre_injected(extracted, pre)
    assert [f.text for f in merged.facts] == ["primary", "secondary"]


def test_merge_prepends_quotes_and_keywords():
    pre = ExtractionResult(
        facts=[],
        quotes=[
            Quote(text="q1", speaker="editor", context="direct", source_urls=["editor-provided"])
        ],
        keywords=["primary_kw"],
    )
    extracted = ExtractionResult(
        facts=[],
        quotes=[Quote(text="q2", speaker="?", context="bio", source_urls=[])],
        keywords=["secondary_kw"],
    )
    merged = _merge_pre_injected(extracted, pre)
    assert [q.text for q in merged.quotes] == ["q1", "q2"]
    assert merged.keywords == ["primary_kw", "secondary_kw"]
