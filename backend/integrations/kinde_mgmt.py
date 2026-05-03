"""Kinde Management API client — M2M-authenticated access to org metadata.

Used by the org sync service (E2) when get_current_org sees an org_code from a JWT
that's not yet in our DB. The client fetches the org, the sync service inserts a
row with domain_name=None, and the operator runs `set_org_domain` CLI (E3) to map
it to one of our editorial domains.

Auth: client_credentials grant against `https://{KINDE_DOMAIN}/oauth2/token` with
audience=`https://{KINDE_DOMAIN}/api`. Returns an access_token cached for its
expires_in (~24h on Kinde's defaults). Refresh on first use after expiry.

Construction reads env vars; raises early if any of KINDE_DOMAIN /
KINDE_M2M_CLIENT_ID / KINDE_M2M_CLIENT_SECRET is missing.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from pydantic import BaseModel


class KindeOrg(BaseModel):
    """Subset of Kinde's organization payload that we actually persist.

    Kinde returns more fields (logo, billing, etc.) — we only carry what's needed
    for the orgs table.
    """

    code: str  # internal Kinde id, e.g. 'org_bfe11034f908' — appears in JWT org_codes
    name: str
    external_id: str | None = None  # operator-set alias, e.g. 'styl_fm_main'
    handle: str | None = None


class KindeManagementClient:
    """Async client for Kinde Management API.

    Methods perform a single REST call each. Token is acquired lazily on first call
    and cached until ~30s before expiry to avoid 401 races.
    """

    def __init__(self) -> None:
        self._domain = os.environ.get("KINDE_DOMAIN", "").strip().rstrip("/")
        self._client_id = os.environ.get("KINDE_M2M_CLIENT_ID", "").strip()
        self._client_secret = os.environ.get("KINDE_M2M_CLIENT_SECRET", "").strip()
        if not all([self._domain, self._client_id, self._client_secret]):
            raise RuntimeError(
                "KindeManagementClient requires KINDE_DOMAIN, KINDE_M2M_CLIENT_ID, "
                "KINDE_M2M_CLIENT_SECRET in env."
            )
        self._token: str | None = None
        self._token_expires_at: float = 0.0  # monotonic seconds

    @property
    def base_url(self) -> str:
        return f"https://{self._domain}"

    async def _get_token(self) -> str:
        """Return a valid M2M access_token; refresh when within 30s of expiry."""
        now = time.monotonic()
        if self._token and now < self._token_expires_at - 30:
            return self._token
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "audience": f"{self.base_url}/api",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = now + int(payload.get("expires_in", 3600))
        assert self._token is not None
        return self._token

    async def _get(self, path: str) -> dict[str, Any]:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}{path}", headers={"Authorization": f"Bearer {token}"}
            )
            resp.raise_for_status()
            return resp.json()

    async def get_organization(self, code: str) -> KindeOrg | None:
        """Fetch one org by code. Returns None on 404 (not found in Kinde)."""
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/organization?code={code}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
        # Kinde wraps in either {"organization": {...}} or returns the dict directly,
        # depending on endpoint version. Handle both.
        org = data.get("organization") if isinstance(data.get("organization"), dict) else data
        return KindeOrg(
            code=org["code"],
            name=org.get("name") or org["code"],
            external_id=org.get("external_id"),
            handle=org.get("handle"),
        )

    async def list_organizations(self) -> list[KindeOrg]:
        """List all orgs in this Kinde workspace. Used for sanity scripts / smoke tests."""
        data = await self._get("/api/v1/organizations")
        return [
            KindeOrg(
                code=o["code"],
                name=o.get("name") or o["code"],
                external_id=o.get("external_id"),
                handle=o.get("handle"),
            )
            for o in data.get("organizations", [])
        ]
