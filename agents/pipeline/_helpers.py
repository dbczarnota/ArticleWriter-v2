# agents/pipeline/_helpers.py
"""Stage-agnostic helpers used across the pipeline orchestration.

Date filtering, social-media URL extraction (from search results AND from
scraped content), article ranking by extraction contribution, and extraction
merging. All pure / stateless — no IO, no LLM calls. Pulled out of runner.py
to keep the orchestration entry point focused on flow control.
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal

import logfire
from pydantic_ai import Agent, BinaryContent

from agents._base.config import ExtractionAgentConfig
from agents._base.resilient import run_with_fallback
from agents._base.run_context import record_agent_call
from agents._base.types import EmbedCandidate, Fact, ParsedArticle, Quote
from agents.extraction.agent import ExtractionOutput, ExtractionResult


def filter_by_date(
    articles: list[ParsedArticle],
    cutoff_days: int,
    manual_urls: set[str],
) -> tuple[list[ParsedArticle], dict[str, str]]:
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC).date() - timedelta(days=cutoff_days)
    kept: list[ParsedArticle] = []
    reasons: dict[str, str] = {}
    for article in articles:
        if article.url in manual_urls:
            kept.append(article)
            continue
        if article.publication_date is None:
            kept.append(article)
            continue
        try:
            pub = datetime.fromisoformat(article.publication_date).date()
        except ValueError:
            kept.append(article)
            continue
        if pub < cutoff:
            reasons[article.url] = f"Too old: {pub}"
        else:
            kept.append(article)
    return kept, reasons


_SocialSource = Literal["youtube", "twitter", "tiktok", "instagram", "facebook", "reddit"]

_SOCIAL_DOMAINS: dict[str, _SocialSource] = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "reddit.com": "reddit",
}


def extract_social_from_search(
    results: list,
) -> tuple[list, list[EmbedCandidate]]:
    """Split search results into (scrapable, social_embed_candidates).

    Social media URLs are useless to scrape but valuable as embeds.
    """
    from urllib.parse import urlparse

    scrapable: list = []
    embeds: list[EmbedCandidate] = []
    for r in results:
        host = urlparse(r.url).netloc.removeprefix("www.")
        source: _SocialSource | None = None
        for domain, src in _SOCIAL_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                source = src
                break
        if source:
            embeds.append(
                EmbedCandidate(
                    url=r.url,
                    title=r.title,
                    source=source,
                    description=r.snippet or None,
                )
            )
        else:
            scrapable.append(r)
    return scrapable, embeds


_SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:youtube\.com/(?:watch|shorts|embed)[^\s\)\]\"'<>]*"
    r"|youtu\.be/[^\s\)\]\"'<>]+"
    r"|twitter\.com/\w+/status/[^\s\)\]\"'<>]+"
    r"|x\.com/\w+/status/[^\s\)\]\"'<>]+"
    r"|tiktok\.com/@[^\s\)\]\"'<>/]+/video/[^\s\)\]\"'<>]+"
    r"|instagram\.com/(?:p|reel|tv)/[^\s\)\]\"'<>/]+"
    r"|facebook\.com/(?:[^/]+/(?:posts|videos|reels)/|watch/\?v=)[^\s\)\]\"'<>]+"
    r"|reddit\.com/r/[^\s\)\]\"'<>]+)",
    re.IGNORECASE,
)


def normalize_social_url(url: str) -> str:
    """Convert embed/shortlink forms to canonical watch URLs."""
    # youtube.com/embed/VIDEO_ID → youtube.com/watch?v=VIDEO_ID
    m = re.match(r"(https?://(?:www\.)?youtube\.com)/embed/([A-Za-z0-9_-]+)", url, re.IGNORECASE)
    if m:
        return f"{m.group(1)}/watch?v={m.group(2)}"
    return url


def extract_social_from_content(
    pages: list,
) -> list[EmbedCandidate]:
    """Extract social media URLs embedded in scraped competitor article content.

    Regex-only, zero LLM cost. Complements extract_social_from_search (which
    catches top-level social URLs) by surfacing embeds mentioned within articles.
    """
    from urllib.parse import urlparse

    seen: set[str] = set()
    candidates: list[EmbedCandidate] = []
    for page in pages:
        for match in _SOCIAL_URL_RE.finditer(page.content):
            url = normalize_social_url(match.group(0).rstrip(".,;)"))
            if url in seen:
                continue
            seen.add(url)
            host = urlparse(url).netloc.removeprefix("www.")
            source: _SocialSource | None = None
            for domain, src in _SOCIAL_DOMAINS.items():
                if host == domain or host.endswith("." + domain):
                    source = src
                    break
            if source:
                candidates.append(
                    EmbedCandidate(
                        url=url,
                        title=url,
                        source=source,
                        competitor_source_url=page.url,
                    )
                )
    return candidates


def rank_articles_by_extraction(
    articles: list[ParsedArticle], extraction: ExtractionResult
) -> list[ParsedArticle]:
    """Sort parsed articles by how much they contributed to the extraction.

    A fact counts twice as much as a quote (facts are more directly load-bearing for
    fact-checking; quotes are also ranked but less aggressively). Articles that didn't
    contribute anything fall to the end in their original order. Reviewer's competitor
    coverage is taken from the top of this list.
    """
    from collections import Counter

    score: Counter[str] = Counter()
    for f in extraction.facts:
        for url in f.source_urls:
            score[url] += 2
    for q in extraction.quotes:
        for url in q.source_urls:
            score[url] += 1
    return sorted(articles, key=lambda a: score[a.url], reverse=True)


def merge_extraction(base: ExtractionResult, extra: ExtractionResult) -> ExtractionResult:
    """Merge two extractions deduping by exact text. When the same fact or
    quote appears on both sides, UNION the source_urls — losing that union
    is what made the same fact appear corroborated only by its first source."""
    base_facts = {f.text: f for f in base.facts}
    for f in extra.facts:
        existing = base_facts.get(f.text)
        if existing is None:
            base_facts[f.text] = f
        else:
            existing.source_urls = list(dict.fromkeys(existing.source_urls + f.source_urls))
    base_quotes = {q.text: q for q in base.quotes}
    for q in extra.quotes:
        existing_q = base_quotes.get(q.text)
        if existing_q is None:
            base_quotes[q.text] = q
        else:
            existing_q.source_urls = list(dict.fromkeys(existing_q.source_urls + q.source_urls))
    merged_keywords = list(dict.fromkeys(base.keywords + extra.keywords))
    return ExtractionResult(
        facts=list(base_facts.values()),
        quotes=list(base_quotes.values()),
        keywords=merged_keywords,
    )


async def extract_facts_from_text(
    raw_text: str,
    topic: str,
    language: str,
    config: ExtractionAgentConfig,
    *,
    source_marker: str = "editor-provided",
    agent_name: str = "text_extraction",
) -> ExtractionResult:
    """Extract facts and quotes from editor-provided raw text.

    Runs a single LLM call using the same ExtractionOutput schema as the main
    extraction agent. All returned items carry source_urls=[source_marker].
    Soft-fails to an empty result on LLM error so the pipeline never halts.

    `source_marker` lets the image-extraction helper reuse this function and
    tag results with "editor-provided-photo" instead of the default text marker.
    """
    sys_prompt = (
        f"You are an editorial assistant. Extract facts and direct quotes from the "
        f"editor-provided text below in the context of the topic: '{topic}'. "
        f"Use '{source_marker}' as the source URL for all items. "
        f"Language: {language}. Be thorough but only include what is explicitly stated."
    )

    def _factory(m: str) -> tuple[Agent[Any, Any], str]:
        return Agent(m, output_type=ExtractionOutput), sys_prompt

    try:
        t0 = time.perf_counter()
        result, model_used = await run_with_fallback(
            (config.model, *config.fallback_models),
            agent_factory=_factory,
            user_prompt=raw_text,
            agent_name=agent_name,
        )
        u = result.usage()
        record_agent_call(
            agent_name,
            model_used,
            u.input_tokens or 0,
            u.output_tokens or 0,
            (time.perf_counter() - t0) * 1000,
        )
        return ExtractionResult(
            facts=[
                Fact(text=f.text, context=f.context, source_urls=[source_marker])
                for f in result.output.facts
            ],
            quotes=[
                Quote(text=q.text, speaker=q.speaker, context=q.context, source_urls=[source_marker])
                for q in result.output.quotes
            ],
            keywords=result.output.keywords,
        )
    except Exception as e:
        logfire.warn(
            f"pipeline.{agent_name}.failed",
            raw_text_len=len(raw_text),
            source_marker=source_marker,
            error_type=type(e).__name__,
            error=str(e),
        )
        return ExtractionResult(facts=[], quotes=[], keywords=[])


# Vision model used to describe images uploaded in the modal step 1.
# Gemini Flash supports image input and is fast enough for an interactive
# extract-preview UX. This mirrors the IG prototype's VISION_MODEL choice.
_IMAGE_VISION_MODEL = "google-gla:gemini-flash-latest"

_IMAGE_VISION_SYSTEM = (
    "Jesteś agentem opisującym zdjęcie dla redakcji serwisu lifestyle. "
    "Twój opis jest BAZĄ FAKTÓW dla pisarza artykułu — musi być bogaty, "
    "konkretny i wierny temu, co widać. "
    "\n\n"
    "Nie identyfikuj twarzy ani osób. Tożsamość osoby zostanie podana w prompcie. "
    "\n\n"
    "Opisuj zarówno to, co widzisz dosłownie (kompozycja, postać, stylizacja, "
    "sceneria), JAK I emocjonalny ładunek kadru — nastrój, klimat, energię, "
    "wyraz mimiki, postawę, dynamikę, vibe. Czytelnicy artykułu mają poczuć, "
    "co czuje osoba na zdjęciu i jaką temperaturę ma kadr. Nie wymyślaj "
    "intencji ('chciała pokazać'), ale możesz nazwać emocje widoczne w mimice "
    "i postawie ('uśmiecha się szeroko, swobodnie', 'wpatruje się prowokująco "
    "w obiektyw', 'pewna siebie poza')."
)

_IMAGE_VISION_USER_TEMPLATE = (
    "Osoba/temat materiału: {topic}.\n\n"
    "Opisz szczegółowo. Strukturyzuj odpowiedź w sekcjach:\n\n"
    "## Ujęcie i kompozycja\n"
    "Plan, kąt, oświetlenie, pora dnia, nastrój światła, dominujące kolory.\n\n"
    "## Postać i emocje\n"
    "Pozycja ciała, gest, układ rąk, mimika. Co dokładnie robi osoba w kadrze "
    "I jaką emocję wyraża — radość, zmysłowość, pewność siebie, prowokacja, "
    "skupienie, dystans. Postawa: napięta, swobodna, dominująca, otwarta.\n\n"
    "## Stylizacja\n"
    "Strój, kolory, fasony, dodatki, fryzura, makijaż. Charakterystyczne detale.\n\n"
    "## Sceneria i tło\n"
    "Lokalizacja, elementy w tle, klimat miejsca.\n\n"
    "## Atmosfera całości\n"
    "Vibe kadru jednym akapitem — co czuje czytelnik patrząc na to zdjęcie. "
    "Glamour, tabloid-sensacja, dolce vita, codzienność, prowokacja, melancholia? "
    "Energia kadru: spokój, dynamika, intensywność, lekkość?\n\n"
    "## Inne szczegóły\n"
    "Cokolwiek pominiętego (rekwizyt, gest, detal stylizacyjny, nietypowy element)."
)


async def extract_facts_from_image(
    image_bytes: bytes,
    media_type: str,
    topic: str,
    language: str,
    config: ExtractionAgentConfig,
) -> ExtractionResult:
    """Two-step image → facts pipeline: a vision LLM produces a rich Polish
    description (composition + emotion/vibe), then `extract_facts_from_text`
    parses that description into structured Fact/Quote items.

    All returned items carry source_urls=["editor-provided-photo"] so the
    instructions agent and the modal step-2 UI can distinguish image-derived
    facts from text-derived ones.

    Soft-fails to an empty result on LLM error — the pipeline never halts on
    image extraction failure (the editor can always paste raw text instead)."""
    with logfire.span(
        "pipeline.image_extraction",
        media_type=media_type,
        image_bytes=len(image_bytes),
        topic=topic,
    ):
        try:
            # Step 1: vision → free-form description
            t0 = time.perf_counter()
            agent = Agent(_IMAGE_VISION_MODEL, system_prompt=_IMAGE_VISION_SYSTEM)
            user_msg = _IMAGE_VISION_USER_TEMPLATE.format(topic=topic)
            vision_result = await agent.run(
                [user_msg, BinaryContent(data=image_bytes, media_type=media_type)]
            )
            description = (
                vision_result.output if isinstance(vision_result.output, str) else str(vision_result.output)
            )
            u = vision_result.usage()
            record_agent_call(
                "image_vision",
                _IMAGE_VISION_MODEL,
                u.input_tokens or 0,
                u.output_tokens or 0,
                (time.perf_counter() - t0) * 1000,
            )
            logfire.info(
                "pipeline.image_extraction.described",
                model=_IMAGE_VISION_MODEL,
                description_len=len(description),
            )

            # Step 2: structured extraction from description, tagged as photo source.
            result = await extract_facts_from_text(
                raw_text=description,
                topic=topic,
                language=language,
                config=config,
                source_marker="editor-provided-photo",
                agent_name="image_text_extraction",
            )
            logfire.info(
                "pipeline.image_extraction.completed",
                facts=len(result.facts),
                quotes=len(result.quotes),
                keywords=len(result.keywords),
            )
            return result
        except Exception as e:
            logfire.warn(
                "pipeline.image_extraction.failed",
                image_bytes=len(image_bytes),
                media_type=media_type,
                error_type=type(e).__name__,
                error=str(e),
            )
            return ExtractionResult(facts=[], quotes=[], keywords=[])
