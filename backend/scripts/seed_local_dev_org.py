"""One-time bootstrap: ensure the `__local_dev__` org exists in Postgres.

Run.py uses this org code when DB_BACKEND=postgres (no Kinde context). The
articles.org_code → orgs.code FK requires the row to exist before the first
`run.py` invocation against Postgres.

Idempotent: safe to run repeatedly. Updates name / domain_name if they diverge.

Usage:
    docker compose up -d db
    DB_BACKEND=postgres uv run python -m backend.scripts.seed_local_dev_org
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    # Imports happen after load_dotenv() so DATABASE_URL is in env.
    from backend.database import get_session_maker
    from backend.repositories.null import LOCAL_DEV_ORG_CODE
    from backend.repositories.postgres import PostgresOrgRepository

    sm = get_session_maker()
    if sm is None:
        raise SystemExit(
            "DATABASE_URL is not set. Either add it to .env or start with "
            "DB_BACKEND=null to skip persistence entirely."
        )
    repo = PostgresOrgRepository(sm)
    org = await repo.create_from_jwt(code=LOCAL_DEV_ORG_CODE, name="Local Dev")
    print(
        f"OK — org '{org.code}' (domain={org.domain_name}) present in DB. "
        "run.py with DB_BACKEND=postgres will now persist."
    )


if __name__ == "__main__":
    asyncio.run(main())
