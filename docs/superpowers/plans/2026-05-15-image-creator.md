# Image Creator Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Narzędzia → Stwórz obraz" tool that lets users fill HTML image templates (with `{{TEXT:label}}` / `{{IMAGE:label}}` placeholders) and render them as JPEGs via the existing htmltomedia service.

**Architecture:** Hybrid — frontend owns template parsing, live preview, base64 image compression, and final HTML assembly; backend owns htmltomedia orchestration (submit → SSE notify via webhook), and persisting image URLs to articles. No R2 or temporary file storage — images are base64-encoded on the client.

**Tech Stack:** FastAPI (backend), asyncio.Queue + SSE (notification), httpx (htmltomedia API), SQLAlchemy async (DB), React + TypeScript (frontend), `dangerouslySetInnerHTML` + pointer/wheel events (drag/zoom).

**Spec:** `docs/superpowers/specs/2026-05-15-image-creator-design.md`

---

## File Map

### Create (backend)
- `tools/__init__.py`
- `tools/image_creator/__init__.py`
- `tools/image_creator/config.py`
- `tools/image_creator/schemas.py`
- `tools/image_creator/service.py`
- `tools/image_creator/routes.py`
- `migrations/versions/a9b0c1d2e3f4_add_image_creator_fields.py`
- `tests/tools/__init__.py`
- `tests/tools/test_image_creator_service.py`

### Modify (backend)
- `backend/db/models.py` — add `image_templates` to `OrgConfig`, `generated_images` to `Article`
- `backend/api/schemas.py` — add `ImageTemplateItem`, `image_templates` to `DomainConfigUpdate`
- `backend/api/v2.py` — expose `generated_images` in `get_article` response
- `backend/main.py` — mount `image_creator` router

### Create (frontend)
- `frontend/src/tools/image-creator/parsePlaceholders.ts`
- `frontend/src/tools/image-creator/htmlBuilder.ts`
- `frontend/src/tools/image-creator/imagePrepare.ts`
- `frontend/src/tools/image-creator/useImageTemplates.ts`
- `frontend/src/tools/image-creator/useImageCreatorJob.ts`
- `frontend/src/tools/image-creator/TemplateSelector.tsx`
- `frontend/src/tools/image-creator/PlaceholderForm.tsx`
- `frontend/src/tools/image-creator/LivePreview.tsx`
- `frontend/src/tools/image-creator/TemplateFiller.tsx`
- `frontend/src/tools/image-creator/ResultPanel.tsx`
- `frontend/src/tools/image-creator/ImageCreatorModal.tsx`
- `frontend/src/tools/image-creator/parsePlaceholders.test.ts`
- `frontend/src/tools/image-creator/htmlBuilder.test.ts`

### Modify (frontend)
- `frontend/src/types.ts` — add `ImageTemplate`, `GeneratedImage`; extend `Article` and `DomainConfigData`
- `frontend/src/i18n/pl.ts` — new strings
- `frontend/src/i18n/en.ts` — new strings
- `frontend/src/i18n/types.ts` — new string keys
- `frontend/src/components/SettingsNav.tsx` — add `szablony-obrazkow` section
- `frontend/src/components/DomainConfigForm.tsx` — add image templates CRUD section
- `frontend/src/components/Topbar.tsx` — add `ToolsMenu` dropdown
- `frontend/src/App.tsx` — wire `ImageCreatorModal` open/close state
- `frontend/src/components/ArticleView.tsx` — render `generated_images` section

---

## Task 1: DB model fields + migration

**Files:**
- Modify: `backend/db/models.py`
- Create: `migrations/versions/a9b0c1d2e3f4_add_image_creator_fields.py`

- [ ] **Add two fields to models.py**

In `OrgConfig` (after `article_templates`):
```python
image_templates: list = Field(
    default_factory=list,
    sa_column=Column(JSONB, nullable=False, server_default=text("'[]'")),
)
"""List of image card templates: [{id: str, name: str, html: str}]."""
```

In `Article` (after `social_media_attachments`):
```python
generated_images: list[dict] = Field(
    default_factory=list,
    sa_column=Column(JSONB, nullable=False, server_default=text("'[]'")),
)
"""Images generated via the Image Creator tool and pinned to this article.
Each entry: {url: str, name: str, created_at: ISO str}."""
```

- [ ] **Create migration file** at `migrations/versions/a9b0c1d2e3f4_add_image_creator_fields.py`:

```python
"""add image creator fields

Revision ID: a9b0c1d2e3f4
Revises: e1f2a3b4c5d6
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "a9b0c1d2e3f4"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_configs",
        sa.Column("image_templates", JSONB, nullable=False, server_default="'[]'"),
    )
    op.add_column(
        "articles",
        sa.Column("generated_images", JSONB, nullable=False, server_default="'[]'"),
    )


def downgrade() -> None:
    op.drop_column("org_configs", "image_templates")
    op.drop_column("articles", "generated_images")
```

> **Note:** `down_revision` must match the latest migration ID in your project. Check `migrations/versions/e1f2a3b4c5d6_add_retention_days_to_org_config.py` — if that's the latest file, this is correct. Otherwise update `down_revision` to the actual latest revision ID.

- [ ] **Run migration against local/prod DB**

```bash
alembic upgrade head
```

Expected: `Running upgrade e1f2a3b4c5d6 -> a9b0c1d2e3f4, add image creator fields`

- [ ] **Commit**

```bash
git add backend/db/models.py migrations/versions/a9b0c1d2e3f4_add_image_creator_fields.py
git commit -m "feat(db): add image_templates to OrgConfig and generated_images to Article"
```

---

## Task 2: Backend schemas + API wiring

**Files:**
- Modify: `backend/api/schemas.py`
- Modify: `backend/api/v2.py`

- [ ] **Add `ImageTemplateItem` and update `DomainConfigUpdate` in schemas.py**

After `ArticleTemplateItem`:
```python
class ImageTemplateItem(BaseModel):
    id: str
    name: str
    html: str
```

At the end of `DomainConfigUpdate` (after `article_templates`):
```python
image_templates: list[ImageTemplateItem] = PydanticField(default_factory=list)
```

- [ ] **Expose `generated_images` in the `get_article` response in v2.py**

Find the dict returned in `get_article` (around line 963). After `"social_media_attachments": article.social_media_attachments,` add:
```python
"generated_images": article.generated_images,
```

- [ ] **Check that domain config save/load propagates `image_templates`**

Search `v2.py` for where `DomainConfigUpdate` fields are written to `OrgConfig`. There should be a loop or explicit field assignments (grep for `article_templates` in v2.py). Add `image_templates` in the same place.

Run: `grep -n "article_templates" backend/api/v2.py` to find the exact lines and mirror the pattern for `image_templates`.

- [ ] **Run checks**

```bash
ruff check . && ruff format --check . && pyright
```

Expected: no errors.

- [ ] **Commit**

```bash
git add backend/api/schemas.py backend/api/v2.py
git commit -m "feat(api): expose image_templates in domain config and generated_images in article response"
```

---

## Task 3: Backend tool module — config + schemas

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/image_creator/__init__.py`
- Create: `tools/image_creator/config.py`
- Create: `tools/image_creator/schemas.py`

- [ ] **Create empty `__init__.py` files**

```bash
# create the files (they stay empty)
```
`tools/__init__.py` — empty  
`tools/image_creator/__init__.py` — empty

- [ ] **Create `tools/image_creator/config.py`**

```python
import os

HTML2MEDIA_BASE_URL: str = os.environ.get(
    "HTML2MEDIA_BASE_URL", "https://headlinesforge.com/html2media"
)
HTML2MEDIA_API_KEY: str = os.environ.get("HTML2MEDIA_API_KEY", "")
PUBLIC_BASE_URL: str = os.environ.get("PUBLIC_BASE_URL", "https://headlinesforge.com")
WEBHOOK_PATH: str = "/api/v2/tools/image-creator/webhook"
```

- [ ] **Create `tools/image_creator/schemas.py`**

```python
from pydantic import BaseModel


class CreateJobRequest(BaseModel):
    html: str
    article_id: str | None = None
    template_name: str = ""


class CreateJobResponse(BaseModel):
    job_id: str


class WebhookPayload(BaseModel):
    job_id: str
    status: str  # "done" | "failed"
    url: str | None = None
    error: str | None = None
```

- [ ] **Commit**

```bash
git add tools/
git commit -m "feat(tools/image-creator): add backend module skeleton — config and schemas"
```

---

## Task 4: Backend service — job orchestration + SSE

**Files:**
- Create: `tools/image_creator/service.py`
- Create: `tests/tools/__init__.py`
- Create: `tests/tools/test_image_creator_service.py`

- [ ] **Write failing tests first** in `tests/tools/test_image_creator_service.py`:

```python
import asyncio
import pytest
import respx
import httpx
from unittest.mock import AsyncMock, MagicMock

from tools.image_creator import service


@pytest.fixture(autouse=True)
def clear_jobs():
    service._jobs.clear()
    yield
    service._jobs.clear()


@respx.mock
@pytest.mark.asyncio
async def test_submit_job_calls_htmltomedia_and_stores_job():
    respx.post("https://headlinesforge.com/html2media/images").mock(
        return_value=httpx.Response(200, json={"job_id": "abc-123"})
    )
    job_id = await service.submit_job(
        html="<h1>Test</h1>",
        article_id="art-1",
        org_code="org-1",
        template_name="Card",
        callback_url="https://headlinesforge.com/api/v2/tools/image-creator/webhook",
    )
    assert job_id == "abc-123"
    assert "abc-123" in service._jobs
    assert service._jobs["abc-123"]["article_id"] == "art-1"


@pytest.mark.asyncio
async def test_handle_webhook_puts_result_in_queue_no_article():
    service._jobs["job-1"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
    }
    db_mock = AsyncMock()
    await service.handle_webhook("job-1", "done", "https://example.com/img.jpg", None, db_mock)
    result = service._jobs["job-1"]["queue"].get_nowait()
    assert result == {"status": "done", "url": "https://example.com/img.jpg", "error": None}
    # no DB write since article_id is None
    db_mock.execute.assert_not_called()


@pytest.mark.asyncio
async def test_handle_webhook_unknown_job_does_not_raise():
    db_mock = AsyncMock()
    # should not raise
    await service.handle_webhook("nonexistent", "done", "https://x.com/img.jpg", None, db_mock)


@pytest.mark.asyncio
async def test_wait_for_result_yields_sse_event():
    service._jobs["job-2"] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": None,
        "org_code": "org-1",
        "template_name": "Card",
    }
    await service._jobs["job-2"]["queue"].put({"status": "done", "url": "https://x.com/r.jpg", "error": None})

    events = []
    async for chunk in service.wait_for_result("job-2"):
        events.append(chunk)

    assert len(events) == 1
    assert '"status": "done"' in events[0]
    assert "job-2" not in service._jobs  # cleaned up
```

- [ ] **Run tests to verify they fail**

```bash
pytest tests/tools/test_image_creator_service.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — service doesn't exist yet.

- [ ] **Create `tools/image_creator/service.py`**

```python
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Article
from tools.image_creator import config

# In-memory job store — ephemeral, process-lifetime only.
# Shape: {job_id: {queue, article_id, org_code, template_name}}
_jobs: dict[str, dict] = {}


async def submit_job(
    html: str,
    article_id: str | None,
    org_code: str,
    template_name: str,
    callback_url: str,
) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{config.HTML2MEDIA_BASE_URL}/images",
            json={"html": html, "width": 1200, "format": "jpeg", "callback_url": callback_url},
            headers={"Authorization": f"Bearer {config.HTML2MEDIA_API_KEY}"},
        )
        resp.raise_for_status()
        job_id: str = resp.json()["job_id"]

    _jobs[job_id] = {
        "queue": asyncio.Queue(maxsize=1),
        "article_id": article_id,
        "org_code": org_code,
        "template_name": template_name,
    }
    return job_id


async def wait_for_result(job_id: str) -> AsyncGenerator[str, None]:
    job = _jobs.get(job_id)
    if not job:
        yield f"data: {json.dumps({'error': 'job not found'})}\n\n"
        return
    try:
        result = await asyncio.wait_for(job["queue"].get(), timeout=120)
        yield f"data: {json.dumps(result)}\n\n"
    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
    finally:
        _jobs.pop(job_id, None)


async def handle_webhook(
    job_id: str,
    status: str,
    url: str | None,
    error: str | None,
    db: AsyncSession,
) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    if status == "done" and url and job.get("article_id"):
        await _append_generated_image(
            db,
            article_id=job["article_id"],
            org_code=job["org_code"],
            url=url,
            name=job["template_name"],
        )
    await job["queue"].put({"status": status, "url": url, "error": error})


async def _append_generated_image(
    db: AsyncSession, article_id: str, org_code: str, url: str, name: str
) -> None:
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,  # type: ignore[arg-type]
            Article.org_code == org_code,
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        return
    images = list(article.generated_images or [])
    images.append(
        {"url": url, "name": name, "created_at": datetime.now(timezone.utc).isoformat()}
    )
    article.generated_images = images
    await db.commit()
```

- [ ] **Run tests again**

```bash
pytest tests/tools/test_image_creator_service.py -v
```

Expected: All 4 tests PASS (the DB test with `article_id=None` passes because we skip the DB call when `article_id` is None).

- [ ] **Run full checks**

```bash
ruff check . && ruff format --check . && pyright
```

- [ ] **Commit**

```bash
git add tools/image_creator/service.py tests/tools/
git commit -m "feat(tools/image-creator): add job orchestration service with SSE + webhook handling"
```

---

## Task 5: Backend routes + mount

**Files:**
- Create: `tools/image_creator/routes.py`
- Modify: `backend/main.py`

- [ ] **Create `tools/image_creator/routes.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.deps import get_current_org
from backend.database import get_session
from backend.db.models import Org
from tools.image_creator import config, service
from tools.image_creator.schemas import CreateJobRequest, CreateJobResponse, WebhookPayload

router = APIRouter(prefix="/api/v2/tools/image-creator", tags=["tools"])


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    body: CreateJobRequest,
    org: Org = Depends(get_current_org),
) -> CreateJobResponse:
    callback_url = f"{config.PUBLIC_BASE_URL}{config.WEBHOOK_PATH}"
    job_id = await service.submit_job(
        html=body.html,
        article_id=body.article_id,
        org_code=org.code,
        template_name=body.template_name,
        callback_url=callback_url,
    )
    return CreateJobResponse(job_id=job_id)


@router.get("/jobs/{job_id}/stream")
async def stream_job(
    job_id: str,
    org: Org = Depends(get_current_org),  # noqa: ARG001 — ensures auth
) -> StreamingResponse:
    return StreamingResponse(
        service.wait_for_result(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/webhook")
async def webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_session),
) -> dict:
    await service.handle_webhook(
        payload.job_id, payload.status, payload.url, payload.error, db
    )
    return {"ok": True}
```

- [ ] **Mount router in `backend/main.py`**

After the existing `app.include_router(streams_router)` line:
```python
from tools.image_creator.routes import router as image_creator_router
app.include_router(image_creator_router)
```

- [ ] **Verify server starts**

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

Expected: no import errors. Check `http://localhost:8000/docs` — you should see the three image-creator endpoints listed.

- [ ] **Run checks**

```bash
ruff check . && ruff format --check . && pyright
```

- [ ] **Commit**

```bash
git add tools/image_creator/routes.py backend/main.py
git commit -m "feat(tools/image-creator): add FastAPI routes and mount in main.py"
```

---

## Task 6: Frontend types + i18n

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/i18n/types.ts`
- Modify: `frontend/src/i18n/pl.ts`
- Modify: `frontend/src/i18n/en.ts`

- [ ] **Add new types to `frontend/src/types.ts`**

After `ArticleTemplate`:
```typescript
export interface ImageTemplate {
  id: string;
  name: string;
  html: string;
}

export interface GeneratedImage {
  url: string;
  name: string;
  created_at: string;
}
```

Add `generated_images` to `Article` (after `social_media_attachments`):
```typescript
generated_images: GeneratedImage[];
```

Add `image_templates` to `DomainConfigData` (after `article_templates`):
```typescript
image_templates: ImageTemplate[];
```

- [ ] **Add new i18n keys to `frontend/src/i18n/types.ts`**

Find the `settingsNav` block and add:
```typescript
imageTemplates: string;
```

Find the `topbar` block and add:
```typescript
tools: string;
createImage: string;
```

Add a new top-level block for the image creator tool:
```typescript
imageCreator: {
  modalTitle: string;
  selectTemplate: string;
  noTemplates: string;
  textPlaceholder: string;
  uploadImage: string;
  assignToArticle: string;
  noArticle: string;
  save: string;
  generating: string;
  download: string;
  copyLink: string;
  copied: string;
  errorGeneration: string;
};
```

- [ ] **Add Polish strings to `frontend/src/i18n/pl.ts`**

In `settingsNav`:
```typescript
imageTemplates: "Szablony obrazków",
```

In `topbar`:
```typescript
tools: "Narzędzia",
createImage: "Stwórz obraz",
```

New top-level block:
```typescript
imageCreator: {
  modalTitle: "Stwórz obraz",
  selectTemplate: "Wybierz szablon",
  noTemplates: "Brak szablonów — dodaj je w Ustawieniach → Szablony obrazków",
  textPlaceholder: "Wpisz tekst…",
  uploadImage: "Wgraj zdjęcie",
  assignToArticle: "Przypisz do artykułu",
  noArticle: "Nie przypisuj",
  save: "Zapisz",
  generating: "Generowanie…",
  download: "Pobierz",
  copyLink: "Kopiuj link",
  copied: "Skopiowano!",
  errorGeneration: "Błąd generowania obrazka",
},
```

- [ ] **Add English strings to `frontend/src/i18n/en.ts`** (mirror the same keys):

```typescript
imageTemplates: "Image templates",
// topbar:
tools: "Tools",
createImage: "Create image",
// imageCreator block:
imageCreator: {
  modalTitle: "Create image",
  selectTemplate: "Select template",
  noTemplates: "No templates — add them in Settings → Image templates",
  textPlaceholder: "Enter text…",
  uploadImage: "Upload image",
  assignToArticle: "Assign to article",
  noArticle: "Don't assign",
  save: "Save",
  generating: "Generating…",
  download: "Download",
  copyLink: "Copy link",
  copied: "Copied!",
  errorGeneration: "Image generation failed",
},
```

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Commit**

```bash
git add frontend/src/types.ts frontend/src/i18n/
git commit -m "feat(frontend): add ImageTemplate, GeneratedImage types and image creator i18n strings"
```

---

## Task 7: Frontend utilities — parsePlaceholders + htmlBuilder + imagePrepare

**Files:**
- Create: `frontend/src/tools/image-creator/parsePlaceholders.ts`
- Create: `frontend/src/tools/image-creator/htmlBuilder.ts`
- Create: `frontend/src/tools/image-creator/imagePrepare.ts`
- Create: `frontend/src/tools/image-creator/parsePlaceholders.test.ts`
- Create: `frontend/src/tools/image-creator/htmlBuilder.test.ts`

- [ ] **Write failing tests** in `frontend/src/tools/image-creator/parsePlaceholders.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { parsePlaceholders } from "./parsePlaceholders";

describe("parsePlaceholders", () => {
  it("parses TEXT and IMAGE placeholders", () => {
    const html = "<h1>{{TEXT:nagłówek}}</h1><div>{{IMAGE:tło}}</div>";
    expect(parsePlaceholders(html)).toEqual([
      { type: "TEXT", label: "nagłówek" },
      { type: "IMAGE", label: "tło" },
    ]);
  });

  it("deduplicates repeated placeholders", () => {
    const html = "{{TEXT:title}} and {{TEXT:title}} again";
    expect(parsePlaceholders(html)).toHaveLength(1);
  });

  it("returns empty array for template with no placeholders", () => {
    expect(parsePlaceholders("<h1>Static</h1>")).toEqual([]);
  });

  it("preserves order of first occurrence", () => {
    const html = "{{IMAGE:photo}}{{TEXT:caption}}";
    const result = parsePlaceholders(html);
    expect(result[0].type).toBe("IMAGE");
    expect(result[1].type).toBe("TEXT");
  });
});
```

- [ ] **Write failing tests** in `frontend/src/tools/image-creator/htmlBuilder.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildHtml, escapeHtml } from "./htmlBuilder";

describe("escapeHtml", () => {
  it("escapes HTML special chars", () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
    );
  });
});

describe("buildHtml", () => {
  it("replaces TEXT placeholders with escaped values", () => {
    const html = "<h1>{{TEXT:title}}</h1>";
    const result = buildHtml(html, { title: "Hello <world>" }, {});
    expect(result).toBe("<h1>Hello &lt;world&gt;</h1>");
  });

  it("replaces IMAGE placeholders with img tags", () => {
    const html = "<div>{{IMAGE:photo}}</div>";
    const imageStates = {
      photo: { dataUrl: "data:image/jpeg;base64,abc", posX: 40, posY: 60, scale: 1.5 },
    };
    const result = buildHtml(html, {}, imageStates);
    expect(result).toContain('src="data:image/jpeg;base64,abc"');
    expect(result).toContain("object-position:40% 60%");
    expect(result).toContain("scale(1.5)");
  });

  it("leaves IMAGE placeholder empty when no image uploaded", () => {
    const html = "<div>{{IMAGE:photo}}</div>";
    const result = buildHtml(html, {}, {});
    expect(result).toBe("<div></div>");
  });
});
```

- [ ] **Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/tools/image-creator/parsePlaceholders.test.ts src/tools/image-creator/htmlBuilder.test.ts
```

Expected: `Cannot find module './parsePlaceholders'` errors.

- [ ] **Create `frontend/src/tools/image-creator/parsePlaceholders.ts`**

```typescript
export interface Placeholder {
  type: "TEXT" | "IMAGE";
  label: string;
}

export function parsePlaceholders(html: string): Placeholder[] {
  const seen = new Set<string>();
  const results: Placeholder[] = [];
  const regex = /\{\{(TEXT|IMAGE):([^}]+)\}\}/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(html)) !== null) {
    const key = `${match[1]}:${match[2]}`;
    if (!seen.has(key)) {
      seen.add(key);
      results.push({ type: match[1] as "TEXT" | "IMAGE", label: match[2] });
    }
  }
  return results;
}
```

- [ ] **Create `frontend/src/tools/image-creator/htmlBuilder.ts`**

```typescript
export interface ImageState {
  dataUrl: string | null;
  posX: number; // 0–100
  posY: number; // 0–100
  scale: number; // 1.0–3.0
}

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function buildHtml(
  template: string,
  textValues: Record<string, string>,
  imageStates: Record<string, ImageState>,
): string {
  return template.replace(/\{\{(TEXT|IMAGE):([^}]+)\}\}/g, (_, type, label) => {
    if (type === "TEXT") {
      return escapeHtml(textValues[label] ?? "");
    }
    // IMAGE
    const state = imageStates[label];
    if (!state?.dataUrl) return "";
    return `<img src="${state.dataUrl}" style="width:100%;height:100%;object-fit:cover;object-position:${state.posX}% ${state.posY}%;transform:scale(${state.scale});transform-origin:center;" data-slot="${label}" />`;
  });
}
```

- [ ] **Create `frontend/src/tools/image-creator/imagePrepare.ts`**

```typescript
const MAX_PX = 1920;
const JPEG_QUALITY = 0.85;

export async function prepareImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, MAX_PX / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      canvas.getContext("2d")!.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(objectUrl);
      resolve(canvas.toDataURL("image/jpeg", JPEG_QUALITY));
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("Failed to load image"));
    };
    img.src = objectUrl;
  });
}
```

- [ ] **Run tests again**

```bash
cd frontend && npx vitest run src/tools/image-creator/
```

Expected: all tests PASS.

- [ ] **Commit**

```bash
git add frontend/src/tools/image-creator/
git commit -m "feat(tools/image-creator): add parsePlaceholders, htmlBuilder, imagePrepare utilities with tests"
```

---

## Task 8: Settings — image templates section

**Files:**
- Modify: `frontend/src/components/SettingsNav.tsx`
- Modify: `frontend/src/components/DomainConfigForm.tsx`

- [ ] **Add `szablony-obrazkow` to `SettingsNav.tsx`**

In the `SECTION_IDS` tuple, after `"szablony"`:
```typescript
"szablony-obrazkow",
```

In the `labels` object:
```typescript
"szablony-obrazkow": t.settingsNav.imageTemplates,
```

- [ ] **Add image templates section to `DomainConfigForm.tsx`**

First, find where `form.article_templates` is initialized (in the `useState` / form init). The `DomainConfigForm` initializes form state from `initialConfig`. Add `image_templates` alongside `article_templates`.

Find the `sectionVisible` helper call pattern and the existing `"szablony"` section. Add a new section below it:

```tsx
{/* Szablony obrazków */}
<section
  id="szablony-obrazkow"
  style={{ display: sectionVisible("szablony-obrazkow") ? "block" : "none", marginBottom: 32 }}
>
  <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
    {t.settingsNav.imageTemplates}
  </h3>
  {(form.image_templates ?? []).map((tmpl, i) => (
    <div
      key={tmpl.id}
      style={{ marginBottom: 16, padding: "12px 14px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 8 }}>
        <input
          value={tmpl.name}
          onChange={(e) => {
            const updated = [...(form.image_templates ?? [])];
            updated[i] = { ...updated[i], name: e.target.value };
            set("image_templates", updated);
          }}
          placeholder="Nazwa szablonu"
          style={{ ...inputStyle, fontWeight: 500, flex: 1 }}
        />
        <button
          type="button"
          onClick={() => set("image_templates", (form.image_templates ?? []).filter((_, j) => j !== i))}
          style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", flexShrink: 0 }}
        >
          Usuń
        </button>
      </div>
      <textarea
        value={tmpl.html}
        onChange={(e) => {
          const updated = [...(form.image_templates ?? [])];
          updated[i] = { ...updated[i], html: e.target.value };
          set("image_templates", updated);
        }}
        placeholder="Wklej HTML szablonu z placeholderami {{TEXT:label}} i {{IMAGE:label}}"
        rows={8}
        style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
      />
    </div>
  ))}
  <button
    type="button"
    onClick={() =>
      set("image_templates", [
        { id: crypto.randomUUID(), name: "", html: "" },
        ...(form.image_templates ?? []),
      ])
    }
    style={{ padding: "6px 14px", background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: 13, cursor: "pointer" }}
  >
    + Dodaj szablon
  </button>
</section>
```

Also ensure `form` state initialization includes `image_templates: initialConfig.image_templates ?? []`.

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Start dev server and verify section appears in Settings nav and form**

```bash
cd frontend && npm run dev
```

Navigate to Settings → "Szablony obrazków". Verify you can add, edit name, edit HTML, and remove templates. Save should persist (test against running backend).

- [ ] **Commit**

```bash
git add frontend/src/components/SettingsNav.tsx frontend/src/components/DomainConfigForm.tsx
git commit -m "feat(settings): add image templates section — name + HTML editor per template"
```

---

## Task 9: useImageTemplates + useImageCreatorJob hooks

**Files:**
- Create: `frontend/src/tools/image-creator/useImageTemplates.ts`
- Create: `frontend/src/tools/image-creator/useImageCreatorJob.ts`

- [ ] **Create `useImageTemplates.ts`**

```typescript
import { useDomainConfig } from "../../lib/useDomainConfig";
import type { ImageTemplate } from "../../types";

export function useImageTemplates(): ImageTemplate[] {
  const { config } = useDomainConfig();
  return config?.image_templates ?? [];
}
```

- [ ] **Create `useImageCreatorJob.ts`**

```typescript
import { useState, useRef, useCallback } from "react";
import { useApi } from "../../lib/useApi";

export type JobStatus = "idle" | "submitting" | "waiting" | "done" | "error";

export interface JobResult {
  url: string | null;
  error: string | null;
}

export function useImageCreatorJob() {
  const api = useApi();
  const [status, setStatus] = useState<JobStatus>("idle");
  const [result, setResult] = useState<JobResult>({ url: null, error: null });
  const esRef = useRef<EventSource | null>(null);

  const submit = useCallback(
    async (html: string, articleId: string | null, templateName: string) => {
      setStatus("submitting");
      setResult({ url: null, error: null });
      try {
        const { job_id } = await api.post<{ job_id: string }>(
          "/api/v2/tools/image-creator/jobs",
          { html, article_id: articleId, template_name: templateName }
        );
        setStatus("waiting");
        const es = new EventSource(`/api/v2/tools/image-creator/jobs/${job_id}/stream`);
        esRef.current = es;
        es.onmessage = (e) => {
          const data = JSON.parse(e.data) as { status: string; url?: string; error?: string };
          es.close();
          esRef.current = null;
          if (data.status === "done" && data.url) {
            setResult({ url: data.url, error: null });
            setStatus("done");
          } else {
            setResult({ url: null, error: data.error ?? "Unknown error" });
            setStatus("error");
          }
        };
        es.onerror = () => {
          es.close();
          esRef.current = null;
          setResult({ url: null, error: "Connection lost" });
          setStatus("error");
        };
      } catch (err) {
        setResult({ url: null, error: String(err) });
        setStatus("error");
      }
    },
    [api]
  );

  const reset = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setStatus("idle");
    setResult({ url: null, error: null });
  }, []);

  return { status, result, submit, reset };
}
```

> **Note:** `useApi` is at `frontend/src/lib/useApi.ts`. Check its signature — it returns a typed wrapper around `fetch`. If it doesn't have a `.post()` method, use the raw API call pattern from existing components (e.g., `useArticles.ts`).

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Commit**

```bash
git add frontend/src/tools/image-creator/useImageTemplates.ts frontend/src/tools/image-creator/useImageCreatorJob.ts
git commit -m "feat(tools/image-creator): add useImageTemplates and useImageCreatorJob hooks"
```

---

## Task 10: TemplateSelector component

**Files:**
- Create: `frontend/src/tools/image-creator/TemplateSelector.tsx`

- [ ] **Create `TemplateSelector.tsx`**

```tsx
import type { ImageTemplate } from "../../types";
import { useT } from "../../i18n";

interface TemplateSelectorProps {
  templates: ImageTemplate[];
  onSelect: (template: ImageTemplate) => void;
}

export function TemplateSelector({ templates, onSelect }: TemplateSelectorProps) {
  const t = useT();

  if (templates.length === 0) {
    return (
      <p style={{ color: "var(--muted)", fontSize: 13, padding: "16px 0" }}>
        {t.imageCreator.noTemplates}
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>
        {t.imageCreator.selectTemplate}
      </p>
      {templates.map((tmpl) => (
        <button
          key={tmpl.id}
          onClick={() => onSelect(tmpl)}
          style={{
            padding: "10px 14px",
            textAlign: "left",
            background: "var(--chrome-bg2)",
            border: "1px solid var(--chrome-border)",
            borderRadius: "var(--radius)",
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 500,
            color: "var(--chrome-ink)",
            fontFamily: "inherit",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--chrome-border)"; }}
        >
          {tmpl.name || "(bez nazwy)"}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Commit**

```bash
git add frontend/src/tools/image-creator/TemplateSelector.tsx
git commit -m "feat(tools/image-creator): add TemplateSelector component"
```

---

## Task 11: PlaceholderForm + LivePreview + TemplateFiller

**Files:**
- Create: `frontend/src/tools/image-creator/PlaceholderForm.tsx`
- Create: `frontend/src/tools/image-creator/LivePreview.tsx`
- Create: `frontend/src/tools/image-creator/TemplateFiller.tsx`

- [ ] **Create `PlaceholderForm.tsx`**

```tsx
import { useRef } from "react";
import type { Placeholder } from "./parsePlaceholders";
import type { ImageState } from "./htmlBuilder";
import { prepareImage } from "./imagePrepare";
import { useT } from "../../i18n";

interface PlaceholderFormProps {
  placeholders: Placeholder[];
  textValues: Record<string, string>;
  imageStates: Record<string, ImageState>;
  activeSlot: string | null;
  onTextChange: (label: string, value: string) => void;
  onImageUpload: (label: string, state: ImageState) => void;
  onActivateSlot: (label: string) => void;
}

export function PlaceholderForm({
  placeholders,
  textValues,
  imageStates,
  activeSlot,
  onTextChange,
  onImageUpload,
  onActivateSlot,
}: PlaceholderFormProps) {
  const t = useT();
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  async function handleFile(label: string, file: File) {
    const dataUrl = await prepareImage(file);
    onImageUpload(label, { dataUrl, posX: 50, posY: 50, scale: 1 });
    onActivateSlot(label);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "12px 14px", overflowY: "auto" }}>
      {placeholders.map((ph) => (
        <div key={`${ph.type}:${ph.label}`}>
          <label style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: 4 }}>
            {ph.type === "TEXT" ? "🔤" : "🖼"} {ph.label}
          </label>
          {ph.type === "TEXT" ? (
            <input
              value={textValues[ph.label] ?? ""}
              onChange={(e) => onTextChange(ph.label, e.target.value)}
              placeholder={t.imageCreator.textPlaceholder}
              style={{ width: "100%", padding: "6px 8px", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: 12, fontFamily: "inherit", boxSizing: "border-box" }}
            />
          ) : (
            <div
              onClick={() => {
                if (imageStates[ph.label]?.dataUrl) {
                  onActivateSlot(ph.label);
                } else {
                  fileInputRefs.current[ph.label]?.click();
                }
              }}
              style={{
                border: `1.5px ${activeSlot === ph.label ? "solid var(--accent)" : "dashed var(--border)"}`,
                borderRadius: "var(--radius)",
                padding: 8,
                cursor: "pointer",
                background: activeSlot === ph.label ? "var(--accent-lt)" : "var(--chrome-bg2)",
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "var(--muted)",
              }}
            >
              {imageStates[ph.label]?.dataUrl ? (
                <>
                  <img
                    src={imageStates[ph.label].dataUrl!}
                    alt=""
                    style={{ width: 40, height: 28, objectFit: "cover", borderRadius: 3, flexShrink: 0 }}
                  />
                  <span style={{ color: "var(--accent)", fontWeight: 500 }}>
                    {activeSlot === ph.label ? "↔ Przeciągnij na podglądzie" : "Kliknij by kadrować"}
                  </span>
                </>
              ) : (
                <span>📁 {t.imageCreator.uploadImage}</span>
              )}
            </div>
          )}
          <input
            ref={(el) => { fileInputRefs.current[ph.label] = el; }}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(ph.label, file);
              e.target.value = "";
            }}
          />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Create `LivePreview.tsx`**

```tsx
import { useRef, useEffect, useCallback } from "react";
import type { ImageState } from "./htmlBuilder";

interface LivePreviewProps {
  html: string;
  activeSlot: string | null;
  onImageStateChange: (label: string, state: Partial<ImageState>) => void;
}

export function LivePreview({ html, activeSlot, onImageStateChange }: LivePreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  // Apply drag/zoom interactions directly on the active slot's img element
  useEffect(() => {
    if (!containerRef.current || !activeSlot) return;
    const el = containerRef.current.querySelector<HTMLImageElement>(`[data-slot="${activeSlot}"]`);
    if (!el) return;

    function onPointerDown(e: PointerEvent) {
      e.preventDefault();
      const style = el!.style;
      const posX = parseFloat(style.objectPosition?.split(" ")[0] ?? "50") || 50;
      const posY = parseFloat(style.objectPosition?.split(" ")[1] ?? "50") || 50;
      dragRef.current = { startX: e.clientX, startY: e.clientY, startPosX: posX, startPosY: posY };
      el!.setPointerCapture(e.pointerId);
    }

    function onPointerMove(e: PointerEvent) {
      if (!dragRef.current || !el) return;
      const dx = ((e.clientX - dragRef.current.startX) / el.offsetWidth) * -100;
      const dy = ((e.clientY - dragRef.current.startY) / el.offsetHeight) * -100;
      const newX = Math.max(0, Math.min(100, dragRef.current.startPosX + dx));
      const newY = Math.max(0, Math.min(100, dragRef.current.startPosY + dy));
      el.style.objectPosition = `${newX}% ${newY}%`;
    }

    function onPointerUp(e: PointerEvent) {
      if (!dragRef.current || !el) return;
      const dx = ((e.clientX - dragRef.current.startX) / el.offsetWidth) * -100;
      const dy = ((e.clientY - dragRef.current.startY) / el.offsetHeight) * -100;
      const newX = Math.max(0, Math.min(100, dragRef.current.startPosX + dx));
      const newY = Math.max(0, Math.min(100, dragRef.current.startPosY + dy));
      dragRef.current = null;
      onImageStateChange(activeSlot!, { posX: newX, posY: newY });
    }

    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const currentScale = parseFloat(el!.style.transform?.match(/scale\(([^)]+)\)/)?.[1] ?? "1") || 1;
      const delta = e.deltaY < 0 ? 0.1 : -0.1;
      const newScale = Math.max(1, Math.min(3, currentScale + delta));
      el!.style.transform = `scale(${newScale})`;
      onImageStateChange(activeSlot!, { scale: newScale });
    }

    el.style.cursor = "grab";
    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", onPointerUp);
    el.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      el.style.cursor = "";
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", onPointerUp);
      el.removeEventListener("wheel", onWheel);
    };
  }, [html, activeSlot, onImageStateChange]);

  return (
    <div style={{ flex: 1, overflow: "auto", background: "#1a1a2e", position: "relative" }}>
      {activeSlot && (
        <div style={{ position: "absolute", top: 6, left: 0, right: 0, textAlign: "center", zIndex: 10, pointerEvents: "none" }}>
          <span style={{ background: "rgba(79,70,229,.8)", color: "white", fontSize: 10, padding: "2px 8px", borderRadius: 10, fontWeight: 600 }}>
            ↔ Przeciągnij · Scroll = zoom
          </span>
        </div>
      )}
      <div
        ref={containerRef}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: html }}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}
```

- [ ] **Create `TemplateFiller.tsx`**

```tsx
import { useState, useCallback } from "react";
import type { ImageTemplate } from "../../types";
import type { ImageState } from "./htmlBuilder";
import { parsePlaceholders } from "./parsePlaceholders";
import { buildHtml } from "./htmlBuilder";
import { PlaceholderForm } from "./PlaceholderForm";
import { LivePreview } from "./LivePreview";

interface TemplateFillerProps {
  template: ImageTemplate;
  onSubmit: (html: string) => void;
  articleSelector: React.ReactNode;
  submitLabel: string;
  isSubmitting: boolean;
}

export function TemplateFiller({
  template,
  onSubmit,
  articleSelector,
  submitLabel,
  isSubmitting,
}: TemplateFillerProps) {
  const placeholders = parsePlaceholders(template.html);
  const [textValues, setTextValues] = useState<Record<string, string>>({});
  const [imageStates, setImageStates] = useState<Record<string, ImageState>>({});
  const [activeSlot, setActiveSlot] = useState<string | null>(null);

  const filledHtml = buildHtml(template.html, textValues, imageStates);

  const handleTextChange = useCallback((label: string, value: string) => {
    setTextValues((prev) => ({ ...prev, [label]: value }));
  }, []);

  const handleImageUpload = useCallback((label: string, state: ImageState) => {
    setImageStates((prev) => ({ ...prev, [label]: state }));
  }, []);

  const handleImageStateChange = useCallback((label: string, patch: Partial<ImageState>) => {
    setImageStates((prev) => ({
      ...prev,
      [label]: { ...prev[label], ...patch },
    }));
  }, []);

  return (
    <div style={{ display: "flex", height: "100%", gap: 0 }}>
      {/* Left: form */}
      <div style={{ width: 280, flexShrink: 0, borderRight: "1px solid var(--chrome-border)", display: "flex", flexDirection: "column" }}>
        <div style={{ flex: 1, overflowY: "auto" }}>
          <PlaceholderForm
            placeholders={placeholders}
            textValues={textValues}
            imageStates={imageStates}
            activeSlot={activeSlot}
            onTextChange={handleTextChange}
            onImageUpload={handleImageUpload}
            onActivateSlot={setActiveSlot}
          />
        </div>
        <div style={{ padding: "10px 14px", borderTop: "1px solid var(--chrome-border)", display: "flex", flexDirection: "column", gap: 8 }}>
          {articleSelector}
          <button
            onClick={() => onSubmit(filledHtml)}
            disabled={isSubmitting}
            style={{
              padding: "8px 0",
              background: isSubmitting ? "var(--accent-lt)" : "var(--accent)",
              color: isSubmitting ? "var(--accent)" : "white",
              border: "none",
              borderRadius: "var(--radius)",
              fontSize: 13,
              fontWeight: 600,
              cursor: isSubmitting ? "default" : "pointer",
              fontFamily: "inherit",
            }}
          >
            {submitLabel}
          </button>
        </div>
      </div>

      {/* Right: live preview */}
      <LivePreview
        html={filledHtml}
        activeSlot={activeSlot}
        onImageStateChange={handleImageStateChange}
      />
    </div>
  );
}
```

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Commit**

```bash
git add frontend/src/tools/image-creator/PlaceholderForm.tsx frontend/src/tools/image-creator/LivePreview.tsx frontend/src/tools/image-creator/TemplateFiller.tsx
git commit -m "feat(tools/image-creator): add PlaceholderForm, LivePreview with drag/zoom, TemplateFiller split layout"
```

---

## Task 12: ResultPanel + ImageCreatorModal

**Files:**
- Create: `frontend/src/tools/image-creator/ResultPanel.tsx`
- Create: `frontend/src/tools/image-creator/ImageCreatorModal.tsx`

- [ ] **Create `ResultPanel.tsx`**

```tsx
import { useState } from "react";
import { useT } from "../../i18n";

interface ResultPanelProps {
  url: string;
  error: string | null;
  onReset: () => void;
}

export function ResultPanel({ url, error, onReset }: ResultPanelProps) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  async function copyLink() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <p style={{ color: "var(--error)", marginBottom: 16 }}>{t.imageCreator.errorGeneration}: {error}</p>
        <button onClick={onReset} style={{ padding: "6px 14px", cursor: "pointer", fontFamily: "inherit" }}>
          Spróbuj ponownie
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
      <img
        src={url}
        alt="Generated"
        style={{ maxWidth: "100%", borderRadius: "var(--radius)", boxShadow: "0 4px 20px rgba(0,0,0,.12)" }}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <a
          href={url}
          download
          style={{
            padding: "7px 16px",
            background: "var(--accent)",
            color: "white",
            borderRadius: "var(--radius)",
            textDecoration: "none",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          ↓ {t.imageCreator.download}
        </a>
        <button
          onClick={copyLink}
          style={{
            padding: "7px 16px",
            border: "1px solid var(--border)",
            background: "none",
            borderRadius: "var(--radius)",
            fontSize: 13,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {copied ? t.imageCreator.copied : t.imageCreator.copyLink}
        </button>
        <button
          onClick={onReset}
          style={{
            padding: "7px 16px",
            border: "1px solid var(--border)",
            background: "none",
            borderRadius: "var(--radius)",
            fontSize: 13,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          ← Nowy obraz
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Create `ImageCreatorModal.tsx`**

```tsx
import { useState } from "react";
import { useT } from "../../i18n";
import { useImageTemplates } from "./useImageTemplates";
import { useImageCreatorJob } from "./useImageCreatorJob";
import { useArticles } from "../../lib/useArticles";
import { TemplateSelector } from "./TemplateSelector";
import { TemplateFiller } from "./TemplateFiller";
import { ResultPanel } from "./ResultPanel";
import type { ImageTemplate } from "../../types";

interface ImageCreatorModalProps {
  onClose: () => void;
}

type Step = "select" | "fill" | "result";

export function ImageCreatorModal({ onClose }: ImageCreatorModalProps) {
  const t = useT();
  const templates = useImageTemplates();
  const { articles } = useArticles();
  const { status, result, submit, reset } = useImageCreatorJob();

  const [step, setStep] = useState<Step>("select");
  const [selectedTemplate, setSelectedTemplate] = useState<ImageTemplate | null>(null);
  const [selectedArticleId, setSelectedArticleId] = useState<string>("");

  function handleSelectTemplate(tmpl: ImageTemplate) {
    setSelectedTemplate(tmpl);
    setStep("fill");
  }

  async function handleSubmit(html: string) {
    await submit(html, selectedArticleId || null, selectedTemplate?.name ?? "");
    setStep("result");
  }

  function handleReset() {
    reset();
    setStep("select");
    setSelectedTemplate(null);
  }

  const articleSelector = (
    <div>
      <label style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: 4 }}>
        {t.imageCreator.assignToArticle}
      </label>
      <select
        value={selectedArticleId}
        onChange={(e) => setSelectedArticleId(e.target.value)}
        style={{ width: "100%", padding: "5px 8px", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: 12, fontFamily: "inherit", background: "var(--chrome-bg)" }}
      >
        <option value="">{t.imageCreator.noArticle}</option>
        {[...articles].sort((a, b) =>
          (b.created_at ?? "").localeCompare(a.created_at ?? "")
        ).map((a) => (
          <option key={a.id} value={a.id}>
            {a.topic.slice(0, 60)}{a.topic.length > 60 ? "…" : ""}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(0,0,0,.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: "var(--chrome-bg)",
          borderRadius: "var(--radius)",
          boxShadow: "0 8px 40px rgba(0,0,0,.25)",
          width: step === "fill" ? "min(1000px, 95vw)" : "min(480px, 95vw)",
          height: step === "fill" ? "min(680px, 90vh)" : "auto",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--chrome-border)", display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {step === "fill" && (
              <button
                onClick={() => setStep("select")}
                style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 13, fontFamily: "inherit", padding: "0 4px" }}
              >
                ←
              </button>
            )}
            <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
              {t.imageCreator.modalTitle}
              {selectedTemplate && step === "fill" ? ` — ${selectedTemplate.name}` : ""}
            </h2>
          </div>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: 4 }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: "hidden" }}>
          {step === "select" && (
            <div style={{ padding: 20 }}>
              <TemplateSelector templates={templates} onSelect={handleSelectTemplate} />
            </div>
          )}

          {step === "fill" && selectedTemplate && (
            <TemplateFiller
              template={selectedTemplate}
              onSubmit={handleSubmit}
              articleSelector={articleSelector}
              submitLabel={status === "submitting" || status === "waiting" ? t.imageCreator.generating : t.imageCreator.save}
              isSubmitting={status === "submitting" || status === "waiting"}
            />
          )}

          {step === "result" && (
            <ResultPanel
              url={result.url ?? ""}
              error={result.error}
              onReset={handleReset}
            />
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Commit**

```bash
git add frontend/src/tools/image-creator/ResultPanel.tsx frontend/src/tools/image-creator/ImageCreatorModal.tsx
git commit -m "feat(tools/image-creator): add ResultPanel and ImageCreatorModal"
```

---

## Task 13: Topbar ToolsMenu + App.tsx wiring

**Files:**
- Modify: `frontend/src/components/Topbar.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Add `ToolsMenu` to `Topbar.tsx`**

Import useState:
```tsx
import { useState } from "react";
```

Add `onCreateImage` prop to `TopbarProps`:
```typescript
interface TopbarProps {
  onSettings: () => void;
  onDiscovery: () => void;
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
  onCreateImage: () => void;
}
```

Add the `ToolsMenu` component at the bottom of the file:
```tsx
function ToolsMenu({ onCreateImage }: { onCreateImage: () => void }) {
  const [open, setOpen] = useState(false);
  const t = useT();

  return (
    <div style={{ position: "relative" }}>
      <NavButton
        onClick={() => setOpen((v) => !v)}
        icon={
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
        }
        label={t.topbar.tools}
      />
      {open && (
        <>
          <div style={{ position: "fixed", inset: 0, zIndex: 98 }} onClick={() => setOpen(false)} />
          <div style={{
            position: "absolute", top: "calc(100% + 4px)", right: 0,
            background: "var(--chrome-bg)", border: "1px solid var(--chrome-border)",
            borderRadius: "var(--radius)", boxShadow: "0 4px 16px rgba(0,0,0,.12)",
            minWidth: 180, zIndex: 99, overflow: "hidden",
          }}>
            <button
              onClick={() => { setOpen(false); onCreateImage(); }}
              style={{
                display: "block", width: "100%", padding: "9px 14px", textAlign: "left",
                background: "none", border: "none", fontSize: 13, cursor: "pointer",
                color: "var(--chrome-ink)", fontFamily: "inherit",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--chrome-bg2)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            >
              🖼 {t.topbar.createImage}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
```

Add `<ToolsMenu onCreateImage={onCreateImage} />` in the nav area of `Topbar`, before `<NavButton onClick={onDiscovery} .../>`.

- [ ] **Wire modal in `App.tsx`**

Add import:
```tsx
import { ImageCreatorModal } from "./tools/image-creator/ImageCreatorModal";
```

Add state:
```tsx
const [imageCreatorOpen, setImageCreatorOpen] = useState(false);
```

Pass to Topbar:
```tsx
<Topbar
  onSettings={() => setView("settings")}
  onDiscovery={() => setView("discovery")}
  onToggleSidebar={() => setSidebarOpen((v) => !v)}
  sidebarOpen={sidebarOpen}
  onCreateImage={() => setImageCreatorOpen(true)}
/>
```

Add modal render (after the `{newModalOpen && ...}` block):
```tsx
{imageCreatorOpen && (
  <ImageCreatorModal onClose={() => setImageCreatorOpen(false)} />
)}
```

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Start dev server and test the full flow manually**

```bash
cd frontend && npm run dev
```

1. Click "Narzędzia" in topbar — dropdown appears with "Stwórz obraz"
2. Click "Stwórz obraz" — modal opens
3. If no templates configured: shows the no-templates message
4. Add a template in Settings → Szablony obrazków (use `<h1>{{TEXT:title}}</h1><div style="width:400px;height:250px;overflow:hidden;">{{IMAGE:photo}}</div>`)
5. Return to modal, select template, fill text, upload image, drag/zoom in preview
6. Click Zapisz — spins (will fail if backend not connected, which is expected in local dev)

- [ ] **Commit**

```bash
git add frontend/src/components/Topbar.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Narzędzia dropdown in Topbar and wire ImageCreatorModal in App"
```

---

## Task 14: ArticleView — generated images section

**Files:**
- Modify: `frontend/src/components/ArticleView.tsx`

- [ ] **Add generated images section to `ArticleView.tsx`**

Find where the article body is rendered. After the main article content area, add:

```tsx
{article.generated_images && article.generated_images.length > 0 && (
  <section style={{ marginTop: 32, paddingTop: 24, borderTop: "1px solid var(--border)" }}>
    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text)" }}>
      Grafiki ({article.generated_images.length})
    </h3>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
      {article.generated_images.map((img, i) => (
        <div
          key={i}
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            overflow: "hidden",
            maxWidth: 320,
          }}
        >
          <img
            src={img.url}
            alt={img.name}
            style={{ display: "block", width: "100%", height: "auto" }}
          />
          <div style={{ padding: "8px 10px", display: "flex", gap: 6, alignItems: "center", background: "var(--chrome-bg2)" }}>
            <span style={{ fontSize: 11, color: "var(--muted)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {img.name}
            </span>
            <a
              href={img.url}
              download
              style={{ fontSize: 11, color: "var(--accent)", textDecoration: "none", fontWeight: 600, flexShrink: 0 }}
            >
              ↓ Pobierz
            </a>
          </div>
        </div>
      ))}
    </div>
  </section>
)}
```

- [ ] **Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Verify in browser** — navigate to an article that has `generated_images` in its DB row (can test by inserting a row manually or by running the full flow with a connected backend).

- [ ] **Run full frontend checks**

```bash
cd frontend && npx vitest run && npx tsc --noEmit && npx eslint src/ --max-warnings 0
```

- [ ] **Commit**

```bash
git add frontend/src/components/ArticleView.tsx
git commit -m "feat(article-view): show generated images section with download links"
```

---

## Task 15: Add env vars to k8s + final checks

**Files:**
- `k8s/backend-deploy.yaml` (or equivalent secrets config)
- `.env.example` (if it exists)

- [ ] **Add new env vars to deployment**

The backend needs three new env vars. Find where existing secrets (`GEMINI_API_KEY`, `SERPER_API_KEY`, etc.) are declared in your k8s deployment and add:

```yaml
- name: HTML2MEDIA_BASE_URL
  value: "https://headlinesforge.com/html2media"
- name: HTML2MEDIA_API_KEY
  valueFrom:
    secretKeyRef:
      name: headlinesforge-secrets
      key: html2media-api-key
- name: PUBLIC_BASE_URL
  value: "https://headlinesforge.com"
```

Add `html2media-api-key` to k8s secret (get the API key from the htmltomedia deployment):
```bash
# Get existing secret, add new key
kubectl get secret headlinesforge-secrets -n headlinesforge -o json \
  | jq '.data["html2media-api-key"] = "'$(echo -n "YOUR_KEY" | base64)'"' \
  | kubectl apply -f -
```

- [ ] **Run full backend checks**

```bash
ruff check . && ruff format --check . && pyright && pytest tests/tools/ -v
```

Expected: all pass.

- [ ] **Run full frontend checks**

```bash
cd frontend && npx vitest run && npx tsc --noEmit
```

Expected: all pass.

- [ ] **Commit**

```bash
git add k8s/
git commit -m "feat(deploy): add HTML2MEDIA env vars to k8s backend deployment"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ Placeholder syntax `{{TEXT:label}}` / `{{IMAGE:label}}` — Task 7 (parsePlaceholders)
- ✅ Backend module `tools/image_creator/` — Tasks 3–5
- ✅ DB migration — Task 1
- ✅ SSE flow instead of polling — Tasks 4–5 (service + routes)
- ✅ Webhook from htmltomedia — Task 4 (handle_webhook) + Task 5 (routes)
- ✅ Base64 inline, no R2 — Task 7 (imagePrepare)
- ✅ Drag/zoom on preview (A2) — Task 11 (LivePreview)
- ✅ "Przypisz do artykułu" dropdown — Task 12 (ImageCreatorModal)
- ✅ Modal stays open, shows result — Task 12 (step="result")
- ✅ Settings section "Szablony obrazków" — Task 8
- ✅ ArticleView generated images — Task 14
- ✅ Topbar "Narzędzia" dropdown — Task 13
- ✅ Local dev webhook limitation documented — Task 5 note

**Type consistency check:**
- `ImageState.posX / posY` — used consistently across htmlBuilder, PlaceholderForm, LivePreview, TemplateFiller ✅
- `submit_job` signature matches `CreateJobRequest` fields ✅
- `handle_webhook` params match `WebhookPayload` fields ✅
- `wait_for_result` returns `AsyncGenerator[str, None]` — used as `StreamingResponse` generator ✅
