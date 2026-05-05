"""No-op repository implementations.

Used when DB_BACKEND=null — keeps `python run.py` working without Docker / Postgres.
All write methods log briefly to stdout so the user knows persistence was skipped;
all read methods return None / empty list.

Also used in tests where pulling Postgres up is overkill.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.db.models import (
    Article,
    EmbedCandidate,
    Fact,
    FallbackEvent,
    Org,
    OrgConfig,
    Quote,
    UsageEvent,
)

_log = logging.getLogger(__name__)

# Stable seed values used by run.py's NullAuthenticator path so a developer can
# rely on the same identifiers across runs.
LOCAL_DEV_ORG_CODE = "__local_dev__"
LOCAL_DEV_DOMAIN = "styl_fm"
LOCAL_DEV_USER_ID = "local-dev"


class NullArticleRepository:
    """ArticleRepository that doesn't persist. Returns synthetic UUIDs and logs writes."""

    async def create_running(
        self,
        *,
        org_code: str,
        author_user_id: str,
        author_email: str | None = None,
        author_name: str | None = None,
        domain_name: str,
        topic: str,
        has_urls: bool = False,
        has_instructions: bool = False,
    ) -> UUID:
        article_id = uuid4()
        _log.info(
            "[null-repo] create_running article_id=%s org=%s user=%s email=%s name=%r topic=%r",
            article_id,
            org_code,
            author_user_id,
            author_email,
            author_name,
            topic[:80],
        )
        return article_id

    async def complete(
        self,
        article_id: UUID,
        *,
        status: str = "done",
        html: str,
        alternative_titles: list[str],
        followup_topics: list[str],
        sources: list[str],
        facts: list[Fact],
        quotes: list[Quote],
        embed_candidates: list[EmbedCandidate],
        usage_events: list[UsageEvent],
        fallback_events: list[FallbackEvent],
        pipeline_timing: dict[str, float],
        errors: list[dict[str, str]],
        total_duration_ms: float,
    ) -> None:
        _log.info(
            "[null-repo] complete article_id=%s status=%s html_len=%d facts=%d quotes=%d "
            "embeds=%d usage=%d fallbacks=%d duration_ms=%.0f",
            article_id,
            status,
            len(html),
            len(facts),
            len(quotes),
            len(embed_candidates),
            len(usage_events),
            len(fallback_events),
            total_duration_ms,
        )

    async def mark_failed(
        self,
        article_id: UUID,
        *,
        error_status: str,
        errors: list[dict[str, str]],
        insufficient_sources_detail: dict | None = None,
    ) -> None:
        _log.info(
            "[null-repo] mark_failed article_id=%s status=%s errors=%d insufficient=%s",
            article_id,
            error_status,
            len(errors),
            bool(insufficient_sources_detail),
        )

    async def get(self, article_id: UUID, *, org_code: str) -> Article | None:
        _log.debug("[null-repo] get article_id=%s org=%s -> None", article_id, org_code)
        return None

    async def list_by_org(
        self, *, org_code: str, limit: int = 20, offset: int = 0
    ) -> list[Article]:
        _log.debug(
            "[null-repo] list_by_org org=%s limit=%d offset=%d -> []", org_code, limit, offset
        )
        return []

    async def set_pipeline_stage(self, article_id: UUID, stage: str | None) -> None:
        pass  # no-op for null backend

    async def set_marked_done(
        self,
        article_id: UUID,
        *,
        org_code: str,
        marked_done: bool,
        marked_done_by_name: str | None = None,
    ) -> None:
        _log.debug(
            "[null-repo] set_marked_done article_id=%s org=%s done=%s (no-op)",
            article_id,
            org_code,
            marked_done,
        )


class NullOrgRepository:
    """OrgRepository that returns a hardcoded local-dev org, so run.py + NullAuth still works."""

    def __init__(self) -> None:
        self._local_dev = Org(
            code=LOCAL_DEV_ORG_CODE,
            domain_name=LOCAL_DEV_DOMAIN,
            name="Local Dev",
            kinde_org_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def create_from_jwt(self, *, code: str, name: str) -> Org:
        _log.info("[null-repo] create_from_jwt code=%s name=%r", code, name)
        return Org(
            code=code,
            domain_name=code,
            name=name,
            kinde_org_id=code,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def get(self, code: str) -> Org | None:
        if code == LOCAL_DEV_ORG_CODE:
            return self._local_dev
        return None

    async def set_domain_name(self, code: str, domain_name: str) -> None:
        if code == LOCAL_DEV_ORG_CODE:
            self._local_dev.domain_name = domain_name
            self._local_dev.updated_at = datetime.now(UTC)

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        if LOCAL_DEV_ORG_CODE in user_org_codes:
            return [self._local_dev]
        return []


class NullOrgConfigRepository:
    """Returns hardcoded styl_fm defaults for offline run.py path.

    Text fields (guidelines, html_format, reflection_stance) are empty because
    offline runs don't need them — the pipeline produces output with bare defaults.
    """

    async def get(self, org_code: str) -> OrgConfig | None:
        return OrgConfig(
            org_code=org_code,
            description="Polski portal lifestyle/celebryci. Clickbait, emocje, krótkie artykuły.",
            language="pl",
            target_word_count=600,
            max_facts=8,
            max_quotes=3,
            search_freshness="qdr:w",
            num_queries=3,
            max_results=5,
            min_source_signals=4,
            max_pages_to_scrape=10,
            youtube_search=True,
            twitter_search=True,
            facebook_search=False,
            news_search=True,
            tiktok_search=True,
            instagram_search=True,
            reddit_search=True,
            media_search_languages=["en", "pl"],
            media_search_num=5,
            media_search_max_query_tiers=2,
            youtube_sort_by_date=True,
            reflection_context_articles=2,
            guidelines="",
            html_format="",
            reflection_stance="",
            reflection_rounds=1,
            example_articles=[],
            example_titles=[],
            agent_models={},
            agent_fallback_models={},
        )

    async def upsert(self, config: OrgConfig) -> OrgConfig:
        return config

    async def create_default(self, org_code: str) -> OrgConfig:
        return OrgConfig(org_code=org_code)
