"""Authenticator boundary — application code talks to this protocol, not to Kinde directly.

Two implementations:
- NullAuthenticator (this file)  — for run.py and tests, returns hardcoded local-dev user
- KindeAuthenticator (D3)        — verifies a JWT against Kinde's JWKS

Pattern lifted from prawnik-ai-v2/backend/auth.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    """Result of `Authenticator.authenticate(token)`.

    Fields are sourced from the JWT for KindeAuthenticator; constants for NullAuthenticator.
    """

    id: str
    """User identifier (Kinde `sub` claim). Stable across orgs."""

    email: str | None = None
    """Kinde email claim if present, else None."""

    org_codes: list[str]
    """All orgs this user belongs to (Kinde `org_codes` claim).
    Used by get_current_org dependency to verify the X-Org-Code header is allowed."""

    current_org_name: str | None = None
    """Display name for the org the user is currently logged into (Kinde `org_name`
    claim if exposed in the access token). Used as the seed value for `Org.name`
    when get_current_org auto-bootstraps a new tenant. May be None — get_current_org
    falls back to the org code in that case."""


class Authenticator(Protocol):
    """Verify a bearer token and return the user."""

    async def authenticate(self, token: str) -> AuthenticatedUser:
        """Decode + validate the token. Raise on invalid/expired/missing-claims.

        Implementations:
        - NullAuthenticator: ignores `token`, returns the local-dev user.
        - KindeAuthenticator: validates JWT signature against Kinde JWKS, verifies
          aud/iss/exp, extracts user fields. Raises HTTPException(401) on any failure.
        """
        ...


class NullAuthenticator:
    """Returns a hardcoded local-dev user. No JWT validation.

    Used when AUTH_BACKEND=null (default for `python run.py`) and in tests.
    The hardcoded user belongs only to the `__local_dev__` org so the get_current_org
    dependency can resolve it via NullOrgRepository.
    """

    async def authenticate(self, token: str) -> AuthenticatedUser:
        from backend.repositories.null import LOCAL_DEV_ORG_CODE, LOCAL_DEV_USER_ID

        return AuthenticatedUser(
            id=LOCAL_DEV_USER_ID,
            email=None,
            org_codes=[LOCAL_DEV_ORG_CODE],
        )
