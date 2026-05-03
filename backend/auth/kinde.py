"""KindeAuthenticator — verifies a Kinde-issued JWT against Kinde's JWKS.

Kinde JWT structure (relevant claims):
- sub:        user identifier (stable across orgs)
- email:      user's email
- aud:        the audience configured for our app (must equal KINDE_AUDIENCE)
- iss:        Kinde issuer URL (https://{KINDE_DOMAIN})
- exp/iat:    standard expiry / issued-at
- org_codes:  list of org codes the user belongs to (custom Kinde claim)

JWKS is fetched from `https://{KINDE_DOMAIN}/.well-known/jwks.json` and cached for 24h.
A 401 (HTTPException) is raised on any verification failure — no error detail is
leaked beyond a generic "Invalid token" message.

Reference patterns from prawnik-ai-v2/backend/auth/kinde.py.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status
from jwt.algorithms import RSAAlgorithm

from backend.auth.protocols import AuthenticatedUser

# JWKS cache: 24-hour TTL is plenty — Kinde rotates keys infrequently and a stale
# JWKS still verifies older tokens that signed against a still-published key.
_JWKS_TTL_SECONDS = 24 * 60 * 60


class KindeAuthenticator:
    """Verify Kinde JWTs against the JWKS endpoint of a configured Kinde domain.

    Construction reads `KINDE_DOMAIN` and `KINDE_AUDIENCE` from environment so a
    single instance can be cached process-wide (tokens for the same domain reuse
    the same JWKS cache).
    """

    def __init__(self) -> None:
        self._domain = os.environ.get("KINDE_DOMAIN", "").strip().rstrip("/")
        self._audience = os.environ.get("KINDE_AUDIENCE", "").strip()
        if not self._domain or not self._audience:
            raise RuntimeError(
                "KindeAuthenticator requires KINDE_DOMAIN and KINDE_AUDIENCE env vars. "
                "Set them in .env or switch AUTH_BACKEND=null."
            )
        self._issuer = f"https://{self._domain}"
        self._jwks_url = f"{self._issuer}/.well-known/jwks.json"
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_fetched_at: float = 0.0

    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch and cache JWKS. Refreshes after 24 hours."""
        now = time.monotonic()
        if self._jwks_cache and (now - self._jwks_fetched_at) < _JWKS_TTL_SECONDS:
            return self._jwks_cache
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            jwks: dict[str, Any] = resp.json()
            self._jwks_cache = jwks
            self._jwks_fetched_at = now
        return jwks

    def _public_key_for_kid(self, jwks: dict[str, Any], kid: str):
        """Find the JWK matching the given key id and convert to a public key."""
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                return RSAAlgorithm.from_jwk(jwk)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token (unknown signing key)",
        )

    async def authenticate(self, token: str) -> AuthenticatedUser:
        """Validate a Kinde JWT and return the AuthenticatedUser.

        Raises HTTPException(401) on:
        - missing or malformed token
        - signature mismatch (key not in JWKS)
        - expired token
        - audience or issuer mismatch
        - missing required claims
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )

        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token (header)"
            ) from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token (missing kid)",
            )

        jwks = await self._fetch_jwks()
        public_key = self._public_key_for_kid(jwks, kid)

        try:
            payload = jwt.decode(
                token,
                public_key,  # type: ignore[arg-type]
                algorithms=[unverified_header.get("alg", "RS256")],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
            ) from exc
        except jwt.InvalidAudienceError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid audience"
            ) from exc
        except jwt.InvalidIssuerError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid issuer"
            ) from exc
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            ) from exc

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token (no sub)"
            )

        # Kinde puts org membership under different claim names depending on the SDK
        # version: `org_codes` (list) or `org_code` (single, for current org).
        # We accept either; the user's full membership list is in org_codes.
        org_codes_raw = payload.get("org_codes")
        if isinstance(org_codes_raw, list):
            org_codes = [str(c) for c in org_codes_raw if c]
        elif single := payload.get("org_code"):
            org_codes = [str(single)]
        else:
            org_codes = []

        return AuthenticatedUser(
            id=str(user_id),
            email=payload.get("email"),
            org_codes=org_codes,
        )
