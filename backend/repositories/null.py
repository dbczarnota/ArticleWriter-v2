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
        domain_name: str,
        topic: str,
    ) -> UUID:
        article_id = uuid4()
        _log.info(
            "[null-repo] create_running article_id=%s org=%s user=%s topic=%r",
            article_id,
            org_code,
            author_user_id,
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

    async def upsert_from_kinde(
        self,
        *,
        kinde_org_id: str,
        code: str,
        name: str,
        domain_name: str,
    ) -> Org:
        _log.info(
            "[null-repo] upsert_from_kinde kinde_id=%s code=%s domain=%s",
            kinde_org_id,
            code,
            domain_name,
        )
        return Org(
            code=code,
            domain_name=domain_name,
            name=name,
            kinde_org_id=kinde_org_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    async def get(self, code: str) -> Org | None:
        if code == LOCAL_DEV_ORG_CODE:
            return self._local_dev
        return None

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        if LOCAL_DEV_ORG_CODE in user_org_codes:
            return [self._local_dev]
        return []
