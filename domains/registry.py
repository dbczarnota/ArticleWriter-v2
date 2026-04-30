# domains/registry.py
from domains._base.config import DomainConfig
from domains.styl_fm.config import STYL_FM_DOMAIN

_REGISTRY: dict[str, DomainConfig] = {
    "styl_fm": STYL_FM_DOMAIN,
}


def load_domain(name: str) -> DomainConfig:
    domain = _REGISTRY.get(name)
    if domain is None:
        raise KeyError(f"Unknown domain: {name!r}. Available: {sorted(_REGISTRY)}")
    return domain
