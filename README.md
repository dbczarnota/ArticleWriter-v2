# ArticleWriter-v2

Multi-agent article generator (pydantic-ai) with FastAPI backend, Postgres
persistence, Kinde auth, and per-tenant editorial domains.

## Quick start (offline / no DB, no auth)

```powershell
uv sync
playwright install
cp .env.example .env  # then fill in SERPER_API_KEY, GEMINI_API_KEY, JINA_API_KEY
uv run python run.py  # one-off pipeline run, output.html written
```

`run.py` runs offline by default (`DB_BACKEND=null`, `AUTH_BACKEND=null`) — no
Docker, no Postgres, no JWT. Articles are NOT persisted; the result is a
single `output.html` file.

## With Postgres persistence

```powershell
docker compose up -d db
uv run alembic upgrade head
uv run python -m backend.scripts.seed_local_dev_org   # one-time, creates __local_dev__ org
$env:DB_BACKEND="postgres"; uv run python run.py      # or set DB_BACKEND=postgres in .env
```

Articles, facts, quotes, usage events, and fallback events all land in
Postgres after the run.

## With auth + multi-tenancy (full server)

```powershell
$env:AUTH_BACKEND="kinde"; $env:DB_BACKEND="postgres"
uv run fastapi dev backend/main.py
```

Set in `.env`:

```
AUTH_BACKEND=kinde
DB_BACKEND=postgres
DATABASE_URL=postgresql+asyncpg://...
KINDE_DOMAIN=...kinde.com
KINDE_AUDIENCE=...
KINDE_M2M_CLIENT_ID=...
KINDE_M2M_CLIENT_SECRET=...
```

After login the frontend hits API endpoints with `Authorization: Bearer <jwt>`
and `X-Org-Code: <org>`. New orgs are auto-synced from Kinde Management API
on first request, but each org needs its editorial domain mapped manually
(once):

```powershell
uv run python -m backend.scripts.set_org_domain --code org_xxx --domain styl_fm
```

## Three orthogonal env switches

| Env var | Values | Default | Effect |
|---------|--------|---------|--------|
| `DB_BACKEND` | `null` / `postgres` | `null` | Persistence layer (`null` = no-op repo) |
| `AUTH_BACKEND` | `null` / `kinde` | `null` | JWT verification (`null` = local-dev user) |
| `LOGFIRE_TOKEN` | string / unset | unset | Observability — only ships spans when set |

These are independent: `AUTH_BACKEND=null + DB_BACKEND=postgres` is valid
(local persistence dev), as is `AUTH_BACKEND=kinde + DB_BACKEND=null` (auth
contract testing without DB).

## Tests

```powershell
uv run pytest -q                              # full suite (skips Docker tests if no Docker)
uv run pytest -q -m "not requires_docker"     # explicitly skip testcontainers tests
```

The repository tests in `tests/backend/test_repositories_postgres.py` spin
up a real Postgres + pgvector container via testcontainers — they skip
gracefully when Docker isn't running.
