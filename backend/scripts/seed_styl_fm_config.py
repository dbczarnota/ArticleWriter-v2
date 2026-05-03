#!/usr/bin/env python
# ruff: noqa: I001
"""Seed org_configs for all styl_fm orgs from current Python config files.

Run once before deploying the H6 changes. Idempotent — uses upsert (session.merge).
Requires DB_BACKEND=postgres and DATABASE_URL to be set.

Usage:
    DB_BACKEND=postgres uv run python -m backend.scripts.seed_styl_fm_config
"""

import asyncio
import os

os.environ.setdefault("DB_BACKEND", "postgres")

from sqlmodel import select

from backend.database import get_session_maker
from backend.db.models import Org, OrgConfig
from domains.styl_fm.config import STYL_FM_DOMAIN  # type: ignore[import]  # domains/ deleted post-seed


async def main() -> None:
    sm = get_session_maker()
    if sm is None:
        raise RuntimeError("DATABASE_URL not set — cannot connect to Postgres.")

    async with sm() as session:
        result = await session.execute(select(Org).where(Org.domain_name == "styl_fm"))
        orgs = result.scalars().all()

        if not orgs:
            print("No orgs with domain_name='styl_fm' found — nothing to seed.")
            return

        for org in orgs:
            config = OrgConfig(
                org_code=org.code,
                description=STYL_FM_DOMAIN.description,
                language=STYL_FM_DOMAIN.language,
                target_word_count=STYL_FM_DOMAIN.target_word_count,
                max_facts=STYL_FM_DOMAIN.max_facts_in_article,
                max_quotes=STYL_FM_DOMAIN.max_quotes_in_article,
                search_freshness=STYL_FM_DOMAIN.default_search_freshness,
                num_queries=STYL_FM_DOMAIN.default_num_queries,
                max_results=STYL_FM_DOMAIN.default_max_results,
                min_source_signals=STYL_FM_DOMAIN.default_min_source_signals,
                max_pages_to_scrape=STYL_FM_DOMAIN.max_pages_to_scrape,
                youtube_search=STYL_FM_DOMAIN.youtube_search,
                twitter_search=STYL_FM_DOMAIN.twitter_search,
                facebook_search=STYL_FM_DOMAIN.facebook_search,
                news_search=STYL_FM_DOMAIN.news_search,
                tiktok_search=STYL_FM_DOMAIN.tiktok_search,
                instagram_search=STYL_FM_DOMAIN.instagram_search,
                reddit_search=STYL_FM_DOMAIN.reddit_search,
                media_search_languages=list(STYL_FM_DOMAIN.media_search_languages),
                media_search_num=STYL_FM_DOMAIN.media_search_num,
                media_search_max_query_tiers=STYL_FM_DOMAIN.media_search_max_query_tiers,
                youtube_sort_by_date=STYL_FM_DOMAIN.youtube_sort_by_date,
                reflection_context_articles=STYL_FM_DOMAIN.default_reflection_context_articles,
                guidelines=STYL_FM_DOMAIN.guidelines,
                html_format=STYL_FM_DOMAIN.html_format,
                reflection_stance=STYL_FM_DOMAIN.reflection_stance,
                example_articles=list(STYL_FM_DOMAIN.example_articles),
            )
            await session.merge(config)
            print(f"  upserted config for org: {org.code}")

        await session.commit()

    print(f"Done — seeded {len(orgs)} org(s).")


asyncio.run(main())
