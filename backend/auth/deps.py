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
from time import time

import logfire
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.protocols import AuthenticatedUser, Authenticator, NullAuthenticator
from backend.repositories import get_org_config_repo, get_org_repo
from backend.repositories.protocols import OrgConfigRepository, OrgRepository

# Window for treating two requests from the same user as one logical
# session. We don't see real login events (those happen on Kinde's hosted
# page); instead we emit `user.session_started` the first time a user_id
# shows up after this gap. Process restart resets the cache, which is
# fine — that's a fresh "session" too.
_SESSION_WINDOW_S = 30 * 60
_recent_users: dict[str, float] = {}

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
    backend = get_auth_backend()
    token = creds.credentials if creds else ""
    if backend == "kinde" and not token:
        logfire.warn("user.auth_failed", reason="missing_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user = await authenticator.authenticate(token)
    except HTTPException as exc:
        if backend == "kinde":
            logfire.warn(
                "user.auth_failed",
                reason="invalid_token",
                status_code=exc.status_code,
            )
        raise
    if backend == "kinde":
        _maybe_emit_session_started(user)
    return user


def _maybe_emit_session_started(user: AuthenticatedUser) -> None:
    """Emit `user.session_started` when this user is first seen (or first
    after `_SESSION_WINDOW_S` of silence). One event per logical session
    rather than per HTTP request — keeps the audit trail readable."""
    now = time()
    last = _recent_users.get(user.id)
    if last is None or now - last > _SESSION_WINDOW_S:
        logfire.info(
            "user.session_started",
            user_id=user.id,
            email=user.email,
            org_codes=list(user.org_codes),
        )
    _recent_users[user.id] = now


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
        logfire.warn(
            "user.org_access_denied",
            user_id=user.id,
            attempted_org_code=org_code,
            user_org_codes=list(user.org_codes),
        )
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
