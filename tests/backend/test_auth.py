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
from backend.db.models import Org, OrgConfig

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


# ---------------------------------------------------------------------------
# get_current_org — auto-bootstrap on first request
# ---------------------------------------------------------------------------


class _FakeOrgRepo:
    def __init__(self) -> None:
        self._by_code: dict[str, Org] = {}
        self.create_calls: list[tuple[str, str]] = []

    async def get(self, code: str) -> Org | None:
        return self._by_code.get(code)

    async def create_from_jwt(self, *, code: str, name: str) -> Org:
        self.create_calls.append((code, name))
        org = self._by_code.get(code)
        if org is None:
            org = Org(code=code, kinde_org_id=code, name=name, domain_name=code)
            self._by_code[code] = org
        return org

    async def list_for_user(self, user_org_codes: list[str]) -> list[Org]:
        return [self._by_code[c] for c in user_org_codes if c in self._by_code]

    async def list_all(self) -> list[Org]:
        return sorted(self._by_code.values(), key=lambda o: o.code)

    async def set_domain_name(self, code: str, domain_name: str) -> None:
        org = self._by_code.get(code)
        if org is not None:
            org.domain_name = domain_name


class _FakeOrgConfigRepo:
    def __init__(self) -> None:
        self.create_default_calls: list[str] = []

    async def get(self, org_code: str) -> OrgConfig | None:
        del org_code
        return None

    async def upsert(self, config: OrgConfig) -> OrgConfig:
        return config

    async def create_default(self, org_code: str) -> OrgConfig:
        self.create_default_calls.append(org_code)
        return OrgConfig(org_code=org_code)


async def test_get_current_org_bootstraps_org_and_config_on_first_request():
    from backend.auth.deps import get_current_org
    from backend.auth.protocols import AuthenticatedUser

    user = AuthenticatedUser(
        id="u1", email="u@x.pl", org_codes=["org_new"], current_org_name="Sport.fm"
    )
    org_repo = _FakeOrgRepo()
    cfg_repo = _FakeOrgConfigRepo()

    org = await get_current_org(
        user=user, org_code="org_new", org_repo=org_repo, config_repo=cfg_repo
    )
    assert org.code == "org_new"
    assert org.name == "Sport.fm"
    assert org.domain_name == "org_new"
    assert org_repo.create_calls == [("org_new", "Sport.fm")]
    assert cfg_repo.create_default_calls == ["org_new"]


async def test_get_current_org_falls_back_to_org_code_when_jwt_has_no_name():
    from backend.auth.deps import get_current_org
    from backend.auth.protocols import AuthenticatedUser

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_new"])
    org_repo = _FakeOrgRepo()
    cfg_repo = _FakeOrgConfigRepo()

    org = await get_current_org(
        user=user, org_code="org_new", org_repo=org_repo, config_repo=cfg_repo
    )
    assert org.name == "org_new"


async def test_get_current_org_returns_existing_without_recreating():
    from backend.auth.deps import get_current_org
    from backend.auth.protocols import AuthenticatedUser

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_x"])
    org_repo = _FakeOrgRepo()
    org_repo._by_code["org_x"] = Org(
        code="org_x", kinde_org_id="org_x", name="Existing", domain_name="org_x"
    )
    cfg_repo = _FakeOrgConfigRepo()

    org = await get_current_org(
        user=user, org_code="org_x", org_repo=org_repo, config_repo=cfg_repo
    )
    assert org.name == "Existing"
    assert org_repo.create_calls == []
    assert cfg_repo.create_default_calls == []


async def test_get_current_org_403_for_non_member():
    from backend.auth.deps import get_current_org
    from backend.auth.protocols import AuthenticatedUser

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])

    with pytest.raises(HTTPException) as exc:
        await get_current_org(
            user=user, org_code="org_b", org_repo=_FakeOrgRepo(), config_repo=_FakeOrgConfigRepo()
        )
    assert exc.value.status_code == 403


async def test_get_current_org_400_when_org_code_header_missing():
    from backend.auth.deps import get_current_org
    from backend.auth.protocols import AuthenticatedUser

    user = AuthenticatedUser(id="u1", email=None, org_codes=["org_a"])

    with pytest.raises(HTTPException) as exc:
        await get_current_org(
            user=user, org_code="", org_repo=_FakeOrgRepo(), config_repo=_FakeOrgConfigRepo()
        )
    assert exc.value.status_code == 400


# Reference for unused imports
_ = os
