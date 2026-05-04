"""FastAPI dependency wrappers for authentication.

Two pivots from env:
- AUTH_BACKEND=null      → NullAuthenticator (default; for run.py + tests)
- AUTH_BACKEND=kinde     → KindeAuthenticator (validates real JWTs)

Endpoints declare:
    @router.get("/me")
    async def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict: ...

`get_current_org` (D5) follows below.
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.protocols import AuthenticatedUser, Authenticator, NullAuthenticator
from backend.repositories import get_org_config_repo, get_org_repo
from backend.repositories.protocols import OrgConfigRepository, OrgRepository

# auto_error=False so the bearer header is optional at the dependency level.
# Authenticator implementations decide what to do with empty token (NullAuth ignores,
# KindeAuth raises 401). This keeps run.py paths uniform.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_backend() -> str:
    """`kinde` or `null`. Default: `null` so a fresh checkout works without Kinde config."""
    return os.environ.get("AUTH_BACKEND", "null").strip().lower() or "null"


@lru_cache(maxsize=1)
def get_authenticator() -> Authenticator:
    """Return the configured Authenticator. Cached for process lifetime.

    KindeAuthenticator construction reads env vars and would raise if KINDE_DOMAIN
    or KINDE_AUDIENCE are missing — that's a config error and should fail loud at
    server startup, not silently default.
    """
    if get_auth_backend() == "kinde":
        from backend.auth.kinde import KindeAuthenticator

        return KindeAuthenticator()
    return NullAuthenticator()


def reset_authenticator_cache() -> None:
    """Clear the cached authenticator. Use in tests when toggling AUTH_BACKEND."""
    get_authenticator.cache_clear()


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authenticator: Authenticator = Depends(get_authenticator),
) -> AuthenticatedUser:
    """Resolve the current user from the Authorization: Bearer <token> header.

    Raises 401 when AUTH_BACKEND=kinde and the bearer token is missing/invalid.
    With AUTH_BACKEND=null the token is ignored — a hardcoded local-dev user is
    returned, mirroring run.py's offline behaviour.
    """
    token = creds.credentials if creds else ""
    if get_auth_backend() == "kinde" and not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await authenticator.authenticate(token)


async def get_current_org(
    user: AuthenticatedUser = Depends(get_current_user),
    org_code: str = Header(alias="X-Org-Code"),
    org_repo: OrgRepository = Depends(get_org_repo),
    config_repo: OrgConfigRepository = Depends(get_org_config_repo),
):
    """Resolve the active org from the X-Org-Code header, auto-bootstrapping
    new tenants on first request.

    Steps:
    1. Verify org_code is in user.org_codes (the JWT claim) — else 403.
       This is the tenant-isolation gate: a user cannot pivot to an org they
       don't belong to even if they happen to know its code.
    2. Look the org up via OrgRepository. If absent: create_from_jwt() with
       the JWT-supplied org name, then create_default() OrgConfig with model
       defaults. Both calls are idempotent.

    Returns the Org row.
    """
    if not org_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Org-Code header is required",
        )
    if org_code not in user.org_codes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not belong to org '{org_code}'",
        )
    org = await org_repo.get(org_code)
    if org is None:
        # First request for this tenant — bootstrap Org row + default config.
        # JWT carries everything we need; Kinde Management API is not consulted.
        seed_name = user.current_org_name or org_code
        org = await org_repo.create_from_jwt(code=org_code, name=seed_name)
        await config_repo.create_default(org_code)
    return org


__all__ = [
    "get_auth_backend",
    "get_authenticator",
    "get_current_org",
    "get_current_user",
    "reset_authenticator_cache",
]
