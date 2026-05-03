"""Authenticator + auth-deps tests.

NullAuthenticator is trivial. KindeAuthenticator path uses a self-signed RSA key
+ mocked JWKS (via respx) to test JWT verification edge cases without hitting
Kinde for real.
"""

from __future__ import annotations

import os
import time

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

from backend.auth.kinde import KindeAuthenticator
from backend.auth.protocols import NullAuthenticator


# ---------------------------------------------------------------------------
# NullAuthenticator
# ---------------------------------------------------------------------------


async def test_null_authenticator_returns_local_dev_user():
    auth = NullAuthenticator()
    user = await auth.authenticate("any-token-or-empty")
    assert user.id == "local-dev"
    assert user.email is None
    assert user.org_codes == ["__local_dev__"]


async def test_null_authenticator_ignores_token():
    auth = NullAuthenticator()
    u1 = await auth.authenticate("")
    u2 = await auth.authenticate("Bearer eyJhbGciOiJ...invalid")
    assert u1.id == u2.id == "local-dev"


# ---------------------------------------------------------------------------
# KindeAuthenticator — fixtures for fake JWKS + token signing
# ---------------------------------------------------------------------------

_KID = "test-kid-001"
_DOMAIN = "test.kinde.example"
_AUDIENCE = "test-audience"


@pytest.fixture(autouse=True)
def kinde_env(monkeypatch):
    """Set Kinde env vars for KindeAuthenticator construction."""
    monkeypatch.setenv("KINDE_DOMAIN", _DOMAIN)
    monkeypatch.setenv("KINDE_AUDIENCE", _AUDIENCE)
    monkeypatch.setenv("KINDE_M2M_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("KINDE_M2M_CLIENT_SECRET", "test-secret")


@pytest.fixture
def rsa_keypair():
    """Generate a fresh RSA keypair for signing fake JWTs."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public = key.public_key()
    return private_pem, public, key


@pytest.fixture
def jwks_payload(rsa_keypair):
    """Build a JWKS document advertising the test public key under _KID."""
    _, public, _ = rsa_keypair
    jwk = RSAAlgorithm.to_jwk(public, as_dict=True)
    jwk["kid"] = _KID
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    return {"keys": [jwk]}


def _sign(claims: dict, private_pem: bytes, kid: str = _KID) -> str:
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})


def _base_claims(**overrides):
    now = int(time.time())
    claims = {
        "sub": "user_test_123",
        "email": "test@example.com",
        "aud": _AUDIENCE,
        "iss": f"https://{_DOMAIN}",
        "iat": now,
        "exp": now + 3600,
        "org_codes": ["org_test1", "org_test2"],
    }
    claims.update(overrides)
    return claims


# ---------------------------------------------------------------------------
# KindeAuthenticator — tests
# ---------------------------------------------------------------------------


async def test_kinde_authenticator_valid_token(rsa_keypair, jwks_payload):
    private_pem, _, _ = rsa_keypair
    token = _sign(_base_claims(), private_pem)

    with respx.mock:
        respx.get(f"https://{_DOMAIN}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks_payload)
        )
        auth = KindeAuthenticator()
        user = await auth.authenticate(token)

    assert user.id == "user_test_123"
    assert user.email == "test@example.com"
    assert user.org_codes == ["org_test1", "org_test2"]


async def test_kinde_authenticator_expired_token_raises_401(rsa_keypair, jwks_payload):
    private_pem, _, _ = rsa_keypair
    token = _sign(_base_claims(exp=int(time.time()) - 60), private_pem)

    with respx.mock:
        respx.get(f"https://{_DOMAIN}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks_payload)
        )
        auth = KindeAuthenticator()
        with pytest.raises(HTTPException) as exc:
            await auth.authenticate(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


async def test_kinde_authenticator_wrong_audience_raises_401(rsa_keypair, jwks_payload):
    private_pem, _, _ = rsa_keypair
    token = _sign(_base_claims(aud="other-audience"), private_pem)

    with respx.mock:
        respx.get(f"https://{_DOMAIN}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks_payload)
        )
        auth = KindeAuthenticator()
        with pytest.raises(HTTPException) as exc:
            await auth.authenticate(token)
    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()


async def test_kinde_authenticator_wrong_issuer_raises_401(rsa_keypair, jwks_payload):
    private_pem, _, _ = rsa_keypair
    token = _sign(_base_claims(iss="https://imposter.example"), private_pem)

    with respx.mock:
        respx.get(f"https://{_DOMAIN}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks_payload)
        )
        auth = KindeAuthenticator()
        with pytest.raises(HTTPException) as exc:
            await auth.authenticate(token)
    assert exc.value.status_code == 401
    assert "issuer" in exc.value.detail.lower()


async def test_kinde_authenticator_unknown_kid_raises_401(rsa_keypair, jwks_payload):
    private_pem, _, _ = rsa_keypair
    token = _sign(_base_claims(), private_pem, kid="unknown-kid")

    with respx.mock:
        respx.get(f"https://{_DOMAIN}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks_payload)
        )
        auth = KindeAuthenticator()
        with pytest.raises(HTTPException) as exc:
            await auth.authenticate(token)
    assert exc.value.status_code == 401


async def test_kinde_authenticator_empty_token_raises_401():
    auth = KindeAuthenticator()
    with pytest.raises(HTTPException) as exc:
        await auth.authenticate("")
    assert exc.value.status_code == 401


async def test_kinde_authenticator_accepts_org_code_singular(rsa_keypair, jwks_payload):
    """Some Kinde SDK versions emit `org_code` (single) instead of `org_codes` (list)."""
    private_pem, _, _ = rsa_keypair
    claims = _base_claims()
    del claims["org_codes"]
    claims["org_code"] = "org_only_one"
    token = _sign(claims, private_pem)

    with respx.mock:
        respx.get(f"https://{_DOMAIN}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json=jwks_payload)
        )
        auth = KindeAuthenticator()
        user = await auth.authenticate(token)

    assert user.org_codes == ["org_only_one"]


async def test_kinde_authenticator_missing_env_raises_runtime_error(monkeypatch):
    """KindeAuthenticator construction fails fast when env vars are missing."""
    monkeypatch.delenv("KINDE_DOMAIN", raising=False)
    monkeypatch.delenv("KINDE_AUDIENCE", raising=False)
    with pytest.raises(RuntimeError, match="KINDE_DOMAIN"):
        KindeAuthenticator()


# ---------------------------------------------------------------------------
# get_auth_backend factory
# ---------------------------------------------------------------------------


def test_get_auth_backend_default_is_null(monkeypatch):
    monkeypatch.delenv("AUTH_BACKEND", raising=False)
    from backend.auth.deps import get_auth_backend

    assert get_auth_backend() == "null"


def test_get_auth_backend_explicit_kinde(monkeypatch):
    monkeypatch.setenv("AUTH_BACKEND", "kinde")
    from backend.auth.deps import get_auth_backend

    assert get_auth_backend() == "kinde"


def test_get_authenticator_factory_picks_null_by_default(monkeypatch):
    monkeypatch.delenv("AUTH_BACKEND", raising=False)
    from backend.auth.deps import get_authenticator, reset_authenticator_cache
    from backend.auth.protocols import NullAuthenticator as NA

    reset_authenticator_cache()
    auth = get_authenticator()
    reset_authenticator_cache()
    assert isinstance(auth, NA)


# Reference for unused imports
_ = os
