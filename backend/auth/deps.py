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

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.protocols import AuthenticatedUser, Authenticator, NullAuthenticator

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


__all__ = [
    "get_auth_backend",
    "get_authenticator",
    "get_current_user",
    "reset_authenticator_cache",
]
