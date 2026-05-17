# Implementation Plan: Per-Org Source Whitelist + Blacklist for Serper

## Design (confirmed)

- Per-org `source_whitelist` + `source_blacklist` stored on `OrgConfig`.
- Whitelist max **40 domains**, blacklist max **20 domains** (Serper `q` ~2048-char budget).
- First-pass search: applies BOTH whitelist (`(site:a OR site:b)`) and blacklist (`-site:x -site:y`).
- Adaptive search: applies BLACKLIST ONLY (whitelist lifted to recover recall).
- Empty whitelist = no filter; empty blacklist = nothing excluded; independent.
- Subdomains: bare domain `wp.pl` matches all `wp.*` (Google default, accepted).
- Settings UI: two textareas (one domain per line) + live counters `X / 40` and `X / 20`, regex validation `^[a-z0-9.-]+\.[a-z]{2,}$`.
- Observability: log final composed Serper `q` to Logfire as span attribute.

## Out of scope

- Post-filtering results in Python (rejected — hard cap + UI communication instead).
- Soft-priority via prompts to writer/reflection (rejected — too unreliable).
- Per-domain weighting.

---

## Phase 0 — Discovery Summary

**Backend models / repo**
- `OrgConfig` is a SQLModel (mutable) at `backend/db/models.py:323-473`. Template for `text[]` field: `media_search_languages: list[str]` with `sa_column=Column(ARRAY(String()), nullable=False, server_default=text("ARRAY['en'::text]"))`.
- Upsert via `OrgConfigRepository.upsert()` using `session.merge()`. Defaults via `create_default()`.
- API: `GET/PUT /v2/domain-config` at `backend/api/v2.py:1215-1266`; Pydantic schema `DomainConfigUpdate` at `backend/api/schemas.py:173-232`. Update uses `model_dump(exclude_unset=True)` + merge + `OrgConfig(org_code=..., **merged)`.
- Auth dep: `get_current_org` at `backend/auth/deps.py:117-159`.
- Alembic migrations in `migrations/versions/`; template = `f70a4f7ec04a_add_org_configs.py`.

**Search pipeline**
- Serper client: `toolsets/scraping/serper.py` — `search()`, `search_news()` etc. each take `query` as-is and POST to `https://google.serper.dev/search`. No org context flows today.
- Existing Logfire span: `serper.results` from `_log_serper_results()` at lines 20-59 (logs `query`, `endpoint`, `result_count`, `cost_usd`).
- First-pass SearchAgent: `agents/search/agent.py:27-110` — calls `serper_search(query, ...)` at line 89, `serper_search_news` at line 99.
- Adaptive: `agents/pipeline/_adaptive_search.py:144-151` — calls same `serper_search`, wrapped in `pipeline.stage.adaptive_search.serper` span.

**OrgConfig → DomainConfig conversion (key insight)**
- `OrgConfig` (SQLModel) is loaded ONCE at API layer in `backend/api/v2.py:146` (`write_article` endpoint).
- Converted to **frozen** `DomainConfig` dataclass via `to_domain_config()` at `backend/domain.py:112`.
- `DomainConfig` definition: `backend/domain.py:38-111`.
- Runner and adaptive loop both receive the hydrated `DomainConfig` — no runner-level DB load needed.

**Frontend**
- Form: `frontend/src/components/DomainConfigForm.tsx` — `useState` + `set<K>(key, val)` helper, `inputStyle` CSS object, textarea template at lines 166-205, inline error pattern at line 1068.
- API hook: `frontend/src/lib/useDomainConfig.ts:13-43` — native `fetch` via `useApi()`.
- i18n: `frontend/src/i18n/{en,pl}.ts`, typed via `frontend/src/i18n/types.ts`, accessed as `t.domainConfig.<key>`.
- No toast library, no validation library, no live-counter precedent.

**Allowed APIs (verified)**
- `Column(ARRAY(String()), nullable=False, server_default=text("ARRAY[]::text[]"))`
- `op.add_column('org_configs', sa.Column(..., postgresql.ARRAY(sa.String()), ...))`
- `logfire.span(name, **attrs)` and span attribute setters (already used in `serper.py:50`)

**Anti-patterns to avoid**
- Don't invent `org_config` parameter on `serper.search()` — pass only two `tuple[str, ...]`.
- Don't post-filter results in Python.
- Don't apply whitelist in adaptive search — blacklist only.
- Don't store `https://` prefix, paths, ports — sanitize on PUT.

---

## Phase 1 — Domain Filter Composer (pure function)

**Create:** `toolsets/scraping/_serper_q.py`

```python
def compose_serper_q(
    query: str,
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> str:
    """Append `(site:a OR site:b) -site:x -site:y` to query."""
```

Rules:
- Empty include + empty exclude → return `query` unchanged.
- Non-empty include → wrap with `(site:a OR site:b OR ...)`, single OR group.
- Non-empty exclude → append ` -site:x -site:y`.
- Strip whitespace from each domain (defensive).
- Preserve input tuple order (makes Logfire diffs readable).

**Create tests:** `tests/toolsets/test_serper_q.py`
- empty / empty → unchanged
- include only / exclude only / both
- single domain include (no OR needed)
- whitespace stripping
- deterministic order

**Verify:** `pytest tests/toolsets/test_serper_q.py -v` green.

**Anti-pattern guard:** No regex parsing of existing `query` — append only.

---

## Phase 2 — OrgConfig Storage (model + migration)

**2a. Add fields to OrgConfig** at `backend/db/models.py:323-473` (after `media_search_languages`):

```python
source_whitelist: list[str] = Field(
    default_factory=list,
    sa_column=Column(ARRAY(String()), nullable=False, server_default=text("ARRAY[]::text[]")),
)
source_blacklist: list[str] = Field(
    default_factory=list,
    sa_column=Column(ARRAY(String()), nullable=False, server_default=text("ARRAY[]::text[]")),
)
```

**2b. Alembic migration**
```
alembic revision --autogenerate -m "add source_whitelist and source_blacklist to org_config"
```
Verify generated file adds two `postgresql.ARRAY(sa.String())` columns with `server_default=sa.text("ARRAY[]::text[]")`. Drop = `op.drop_column` x2.

**2c. Constants** at top of `backend/api/schemas.py`:
```python
SOURCE_WHITELIST_MAX = 40
SOURCE_BLACKLIST_MAX = 20
```

**Verify:**
- `alembic upgrade head` against local DB succeeds.
- `alembic downgrade -1 && alembic upgrade head` round-trips.
- `OrgConfig()` with no args → both fields = `[]`.

**Anti-pattern guard:** Do NOT use JSONB — repo precedent for text arrays is `ARRAY(String())`.

---

## Phase 3 — API Schema + Endpoint Validation

**3a. Extend `DomainConfigUpdate`** at `backend/api/schemas.py:173-232`:
```python
source_whitelist: list[str] | None = None
source_blacklist: list[str] | None = None
```

Pydantic field validators:
- Strip whitespace, lowercase.
- Drop empty strings.
- Regex match `^[a-z0-9.-]+\.[a-z]{2,}$`.
- Reject `https://` prefix, paths, ports.
- `len(whitelist) <= SOURCE_WHITELIST_MAX` else 422 with `"max 40 domains (Serper query length limit)"`.
- Same for blacklist with max 20.
- Deduplicate (preserve first-seen order).

**3b. Response serializer** — extend `_org_config_to_dict` in `backend/api/v2.py` to include both fields.

**3c. Tests** `tests/api/test_domain_config_source_lists.py`:
- PUT valid lists → 200, persisted, GET returns same.
- PUT 41 domains → 422.
- PUT `"https://wp.pl"` → 422.
- PUT `"wp.pl/news"` → 422.
- PUT empty list → 200, stored as `[]`.
- PUT duplicates → deduplicated.
- Two-org tenant isolation.

**Verify:** `pytest tests/api/test_domain_config_source_lists.py -v` green.

---

## Phase 4 — Plumb to Serper Layer

**4a. Extend `serper.search()` signature** in `toolsets/scraping/serper.py`:
```python
async def search(
    query: str,
    *,
    num: int = 10,
    freshness: str = "qdr:w",
    language: str = "pl",
    api_key: str,
    site_include: tuple[str, ...] = (),
    site_exclude: tuple[str, ...] = (),
) -> list[SearchResult]:
    q_final = compose_serper_q(query, include=site_include, exclude=site_exclude)
    payload = {"q": q_final, ...}
```

Same for `search_news()`. Other variants (`search_videos`, `search_images`, `search_reddit`) — skip unless invoked by the search pipeline; verify by grep.

**4b. Logfire** — extend `_log_serper_results()` (lines 20-59) to emit:
- `serper.q_user` (original query)
- `serper.q_final` (composed query)
- `serper.site_include_count`
- `serper.site_exclude_count`

**4c. Tests** `tests/toolsets/test_serper_search.py` with `respx`:
- Stub Serper, assert payload `q` equals composed string.
- Assert Logfire span has `serper.q_final` attribute.

**Verify:** `pytest tests/toolsets/test_serper_search.py -v` + existing Serper tests still pass.

---

## Phase 5 — Wire DomainConfig → Search Agents → Serper

OrgConfig → DomainConfig conversion happens once at API layer; runner and adaptive loop already receive hydrated `DomainConfig`. No new DB loads.

**5a. Extend `DomainConfig`** at `backend/domain.py:38-111` (frozen dataclass):
```python
source_whitelist: tuple[str, ...] = ()
source_blacklist: tuple[str, ...] = ()
```

**5b. Extend `to_domain_config()`** at `backend/domain.py:112`:
```python
source_whitelist=tuple(config.source_whitelist),
source_blacklist=tuple(config.source_blacklist),
```

**5c. First-pass SearchAgent** at `agents/search/agent.py:89` (and 99): pass `site_include=domain.source_whitelist, site_exclude=domain.source_blacklist`. Add `domain: DomainConfig` to `run_search_agent` signature if not already present — verify by grep.

**5d. Adaptive search** at `agents/pipeline/_adaptive_search.py:144-151`: pass `site_include=()` (whitelist intentionally lifted) and `site_exclude=domain.source_blacklist`. `domain` already in scope at line 36 — no signature change.

**5e. Tests** `tests/agents/test_search_filter_integration.py`:
- Build `DomainConfig` with whitelist + blacklist; run `run_search_agent` with mocked Serper; assert `site_include`/`site_exclude` passed through.
- Same for `adaptive_search_loop`; assert `site_include=()` regardless of whitelist contents.

**Verify:** `pytest tests/agents/ -v`; `ruff check .`, `pyright` clean.

---

## Phase 6 — Frontend Settings UI

**6a. i18n keys** — add to `frontend/src/i18n/{en,pl}.ts` under `domainConfig`:
- `sourceWhitelist`, `sourceWhitelistHint` ("one domain per line, no https://")
- `sourceWhitelistCounter` ("{count} / 40")
- `sourceBlacklist`, `sourceBlacklistHint`, `sourceBlacklistCounter` ("{count} / 20")
- `sourceWhitelistOverLimit` ("max 40 domains — Google search query length limit")
- `sourceWhitelistInvalid` ("invalid domain: {value}")

**6b. Types** — extend `DomainConfigData` in `frontend/src/lib/useDomainConfig.ts` (verify path by grep): `source_whitelist?: string[]; source_blacklist?: string[];`

**6c. Component** — in `DomainConfigForm.tsx`, add a new section (mirror textarea section, lines 166-205). Two textareas:
- Value = `form.source_whitelist?.join("\n") ?? ""`.
- onChange = parse `e.target.value.split("\n").map(s => s.trim()).filter(Boolean)`, then `set("source_whitelist", parsed)`.
- Live counter below: `{count} / 40` — red if over limit.
- Inline validation errors for invalid lines (same regex as backend).
- Disable save button when any field over its limit.

**6d. Verify in browser** (per CLAUDE.md UI rule):
- `npm run dev` in `frontend/`.
- Counter updates live.
- 41st domain blocked + error.
- `https://wp.pl` → validation error.
- Save → reload → values persist.
- Test in PL and EN.

**Anti-pattern guard:** No validation library. Match existing `useState`+`set()` pattern.

---

## Phase 7 — End-to-End Verification

**Backend**
- `ruff check . && ruff format --check . && pyright`
- `pytest tests/toolsets/test_serper_q.py tests/api/test_domain_config_source_lists.py tests/agents/test_search_filter_integration.py -v`
- Full suite: `pytest`

**Frontend**
- `cd frontend && npm run lint && npm run typecheck && npm test`

**Manual smoke (via `.\scripts\dev-prod-db.ps1`)**
- Set whitelist `["wp.pl"]` for a test org → kick off article → Logfire: `serper.results` span should have `serper.q_final` containing `(site:wp.pl)`.
- Set blacklist `["pudelek.pl"]` → adaptive search span: `serper.q_final` contains `-site:pudelek.pl` AND no `site:` (whitelist lifted).
- Empty both → `serper.q_final == serper.q_user`.

**Anti-pattern grep (final sweep)**
- `grep -r "site:.*OR.*site:" backend/` — only matches the composer.
- `grep -r "source_whitelist\|source_blacklist" backend/ frontend/` — coverage check.

**Commit policy:** one logical commit per phase (per CLAUDE.md §5 — each independently reversible).
