"""CLI: map a Kinde org to an editorial domain (operator-run, idempotent).

Two flows:

A) Map an EXISTING DB row (org synced from Kinde via E2 has domain_name="").
   uv run python -m backend.scripts.set_org_domain --code org_bfe11034f908 --domain styl_fm

B) Create + map at once (org not yet synced from Kinde — uses Kinde Management
   API to fetch metadata, then writes the row with domain_name set).
   uv run python -m backend.scripts.set_org_domain --code org_bfe11034f908 --domain styl_fm --fetch-from-kinde

Domain name is stored as-is; config is stored in the org_configs table.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Map a Kinde org_code to an editorial domain.")
    p.add_argument(
        "--code",
        required=True,
        help="Kinde org code (the 'code' field, not 'external_id'). E.g. org_bfe11034f908",
    )
    p.add_argument(
        "--domain",
        required=True,
        help="Editorial domain name. E.g. styl_fm",
    )
    p.add_argument(
        "--fetch-from-kinde",
        action="store_true",
        help="If the org doesn't exist in our DB yet, fetch metadata from Kinde first.",
    )
    return p.parse_args()


async def main() -> None:
    args = _parse_args()

    # Domain config is now stored in org_configs table — no static registry to validate against.

    from sqlmodel import select

    from backend.database import get_db_backend, get_session_maker
    from backend.db.models import Org

    if get_db_backend() != "postgres":
        raise SystemExit(
            "DB_BACKEND must be 'postgres' to run this script "
            "(set DB_BACKEND=postgres in .env or in the shell)."
        )
    sm = get_session_maker()
    if sm is None:
        raise SystemExit("DATABASE_URL is not configured.")

    async with sm() as session:
        result = await session.execute(select(Org).where(Org.code == args.code))
        org = result.scalar_one_or_none()

        if org is None:
            if not args.fetch_from_kinde:
                raise SystemExit(
                    f"Org with code={args.code!r} not in DB. Either:\n"
                    "  - re-run with --fetch-from-kinde to pull metadata from Kinde, OR\n"
                    "  - log into the app once with this org so the auto-sync (E2) creates it."
                )
            from backend.integrations.kinde_mgmt import KindeManagementClient

            client = KindeManagementClient()
            kinde_org = await client.get_organization(args.code)
            if kinde_org is None:
                raise SystemExit(
                    f"Kinde does not have an organization with code={args.code!r}."
                )
            org = Org(
                code=kinde_org.code,
                domain_name=args.domain,
                name=kinde_org.name,
                kinde_org_id=kinde_org.code,
            )
            session.add(org)
            print(f"Created org row from Kinde: {kinde_org.code} -> domain={args.domain}")
        else:
            previous = org.domain_name
            org.domain_name = args.domain
            print(
                f"Updated org {args.code}: domain {previous!r} -> {args.domain!r} "
                f"(name={org.name!r})"
            )

        await session.commit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
