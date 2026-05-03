"""Org sync service — bootstraps an Org row from Kinde when get_current_org
sees a JWT org_code that's not yet in our DB.

Flow:
1. User logs in via Kinde frontend (eventually); JWT contains org_codes claim.
2. User hits a backend endpoint with X-Org-Code header.
3. get_current_org dependency checks DB; if absent, calls sync_org_from_kinde().
4. sync_org_from_kinde fetches the org from Kinde Management API and inserts a
   row with domain_name=None.
5. get_current_org then returns 412 ("not yet mapped to a domain"); operator
   runs `set_org_domain` CLI (E3) to assign the domain.
6. Subsequent requests pass through normally.

The sync only adds NEW orgs — it does not refresh existing ones (orgs.name
update would happen via a separate refresh endpoint, not on every login).

Cached client at module level: a single KindeManagementClient instance is
shared across the process (its access_token cache lives there).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from backend.integrations.kinde_mgmt import KindeManagementClient
from backend.repositories.protocols import OrgRepository

_log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_kinde_client() -> KindeManagementClient:
    """Process-wide cached Kinde Management client."""
    return KindeManagementClient()


async def sync_org_from_kinde(org_code: str, org_repo: OrgRepository) -> bool:
    """Fetch the org from Kinde and upsert into DB. Returns True if synced.

    Returns False (and logs a warning) if Kinde doesn't know the org. The caller
    (get_current_org) will then return 404 / 412 to the user.

    `domain_name` is intentionally left as None (or whatever the existing row had).
    The operator must run `backend.scripts.set_org_domain` to assign it.
    """
    client = _get_kinde_client()
    try:
        kinde_org = await client.get_organization(org_code)
    except Exception as exc:
        _log.warning(
            "Kinde Management API call failed for org_code=%s: %s", org_code, exc
        )
        return False
    if kinde_org is None:
        _log.warning("Kinde does not have an organization with code=%s", org_code)
        return False
    # We pass empty domain_name; PostgresOrgRepository.upsert_from_kinde stores it
    # as the new value if the row is new, or preserves it on update.
    await org_repo.upsert_from_kinde(
        kinde_org_id=kinde_org.code,
        code=kinde_org.code,
        name=kinde_org.name,
        domain_name="",  # operator must set via CLI; get_current_org returns 412 until then
    )
    _log.info("Synced org from Kinde: code=%s name=%r", kinde_org.code, kinde_org.name)
    return True


def reset_kinde_client_cache() -> None:
    """Clear the cached Kinde client. Use in tests when toggling env vars."""
    _get_kinde_client.cache_clear()
