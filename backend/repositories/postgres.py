"""Postgres-backed repository implementations using SQLAlchemy 2.0 async.

Each method opens a session via the session-maker injected at __init__.
Sessions are short-lived: one per call. No long-lived sessions / unit-of-work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlmodel import select

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


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PostgresArticleRepository:
    """ArticleRepository implementation backed by Postgres."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    async def create_running(
        self,
        *,
        org_code: str,
        author_user_id: str,
        author_email: str | None = None,
        domain_name: str,
        topic: str,
    ) -> UUID:
        article = Article(
            org_code=org_code,
            author_user_id=author_user_id,
            author_email=author_email,
            domain_name=domain_name,
            topic=topic,
            status="running",
        )
        async with self._session_maker() as session:
            session.add(article)
            await session.commit()
            await session.refresh(article)
        return article.id

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
        async with self._session_maker() as session:
            article = await session.get(Article, article_id)
            if article is None:
                raise LookupError(f"Article {article_id} not found")
            article.status = status
            article.html = html
            article.alternative_titles = alternative_titles
            article.followup_topics = followup_topics
            article.sources = sources
            article.pipeline_timing = pipeline_timing
            article.errors = errors
            article.total_duration_ms = total_duration_ms
            article.completed_at = _utcnow()

            # Attach children. The caller passes child instances WITHOUT article_id /
            # WITHOUT id; we set them here so the runner doesn't need to know schema.
            for child_list, _ in (
                (facts, Fact),
                (quotes, Quote),
                (embed_candidates, EmbedCandidate),
                (usage_events, UsageEvent),
                (fallback_events, FallbackEvent),
            ):
                for child in child_list:
                    if not getattr(child, "id", None):
                        child.id = uuid4()
                    child.article_id = article_id
                    session.add(child)

            await session.commit()

    async def mark_failed(
        self,
        article_id: UUID,
        *,
        error_status: str,
        errors: list[dict[str, str]],
        insufficient_sources_detail: dict | None = None,
    ) -> None:
        async with self._session_maker() as session:
            article = await session.get(Article, article_id)
            if article is None:
                raise LookupError(f"Article {article_id} not found")
            article.status = error_status
            article.errors = errors
            article.insufficient_sources_detail = insufficient_sources_detail
            article.completed_at = _utcnow()
            await session.commit()

    async def get(self, article_id: UUID, *, org_code: str) -> Article | None:
        async with self._session_maker() as session:
            stmt = (
                select(Article)
                .where(Article.id == article_id, Article.org_code == org_code)
                .options(
                    selectinload(Article.facts),  # type: ignore[arg-type]
                    selectinload(Article.quotes),  # type: ignore[arg-type]
                    selectinload(Article.embed_candidates),  # type: ignore[arg-type]
                    selectinload(Article.usage_events),  # type: ignore[arg-type]
                    selectinload(Article.fallback_events),  # type: ignore[arg-type]
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_org(
        self, *, org_code: str, limit: int = 20, offset: int = 0
    ) -> list[Article]:
        async with self._session_maker() as session:
            stmt = (
                select(Article)
                .where(Article.org_code == org_code)
                .order_by(Article.created_at.desc())  # type: ignore[attr-defined]
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def set_pipeline_stage(self, article_id: UUID, stage: str | None) -> None:
        async with self._session_maker() as session:
            stmt = select(Article).where(Article.id == article_id)
            result = await session.execute(stmt)
            article = result.scalar_one_or_none()
            if article is None:
                return
            article.pipeline_stage = stage
            await session.commit()

    async def set_marked_done(
        self,
        article_id: UUID,
        *,
        org_code: str,
        marked_done: bool,
        marked_done_by_name: str | None = None,
    ) -> None:
        async with self._session_maker() as session:
            stmt = select(Article).where(Article.id == article_id, Article.org_code == org_code)
            result = await session.execute(stmt)
            article = result.scalar_one_or_none()
            if article is None:
                return
            article.marked_done = marked_done
            article.marked_done_by_name = marked_done_by_name if marked_done else None
            await session.commit()


class PostgresOrgRepository:
    """OrgRepository implementation backed by Postgres."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._session_maker = session_maker

    async def upsert_from_kinde(
        self,
        *,
        kinde_org_id: str,
        code: str,
        name: str,
        domain_name: str,
    ) -> Org:
        async with self._session_maker() as session:
            stmt = select(Org).where(Org.kinde_org_id == kinde_org_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is None:
                org = Org(
                    code=code,
                    domain_name=domain_name,
                    name=name,
                    kinde_org_id=kinde_org_id,
                )
                session.add(org)
            else:
                existing.name = name
                existing.domain_name = domain_name
                org = existing
            await session.commit()
            await session.refresh(org)
        return org

    async def get(self, code: str) -> Org | None:
        async with self._session_maker() as session:
            return await session.get(Org, code)

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        if not user_org_codes:
            return []
        async with self._session_maker() as session:
            stmt = select(Org).where(Org.code.in_(user_org_codes)).order_by(Org.name)  # type: ignore[attr-defined]
            result = await session.execute(stmt)
            return list(result.scalars().all())


class PostgresOrgConfigRepository:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        self._sm = session_maker

    async def get(self, org_code: str) -> OrgConfig | None:
        async with self._sm() as session:
            return await session.get(OrgConfig, org_code)

    async def upsert(self, config: OrgConfig) -> OrgConfig:
        config.updated_at = _utcnow()
        async with self._sm() as session:
            merged = await session.merge(config)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def create_default(self, org_code: str) -> OrgConfig:
        async with self._sm() as session:
            existing = await session.get(OrgConfig, org_code)
            if existing is not None:
                return existing
            cfg = OrgConfig(org_code=org_code)
            session.add(cfg)
            await session.commit()
            await session.refresh(cfg)
            return cfg
