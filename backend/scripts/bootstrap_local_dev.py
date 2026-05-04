"""One-time bootstrap for the `__local_dev__` tenant in local Postgres.

`run.py` uses `__local_dev__` as the org code when AUTH_BACKEND=null. The
articles.org_code → orgs.code FK requires the row to exist before any
persistence happens. In production this is unnecessary — the auto-bootstrap
in `get_current_org` handles new tenants on first request. Local-dev has no
JWT path, so we seed the row + default config explicitly.

Idempotent: safe to run repeatedly. Both create_from_jwt and create_default
return the existing rows when present without overwriting user edits.

Usage:
    docker compose up -d db
    DB_BACKEND=postgres uv run python -m backend.scripts.bootstrap_local_dev
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    # Imports happen after load_dotenv() so DATABASE_URL is in env when the
    # repo factory reads it.
    import os

    os.environ.setdefault("DB_BACKEND", "postgres")

    from backend.repositories import get_org_config_repo, get_org_repo
    from backend.repositories.null import LOCAL_DEV_ORG_CODE

    org_repo = get_org_repo()
    config_repo = get_org_config_repo()

    org = await org_repo.create_from_jwt(code=LOCAL_DEV_ORG_CODE, name="Local Dev")
    cfg = await config_repo.create_default(LOCAL_DEV_ORG_CODE)
    print(
        f"OK — org '{org.code}' (domain={org.domain_name}) and OrgConfig "
        f"(language={cfg.language}, target_word_count={cfg.target_word_count}) "
        "ready in DB. run.py with DB_BACKEND=postgres will now persist."
    )


if __name__ == "__main__":
    asyncio.run(main())
