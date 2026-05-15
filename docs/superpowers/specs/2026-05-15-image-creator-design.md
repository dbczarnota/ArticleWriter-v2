# Image Creator Tool — Design Spec

**Date:** 2026-05-15  
**Status:** Approved

## Overview

A new "Narzędzia" (Tools) dropdown in the Topbar nav, containing the first tool: "Stwórz obraz" (Create Image). Users select an HTML template configured per-org, fill in text and image placeholders with a live preview, and render the result via the existing `htmltomedia` external service. The generated image URL is optionally pinned to an article.

---

## 1. Placeholder Syntax

Templates are plain HTML strings stored per-org. Placeholders use the pattern `{{TYPE:label}}`:

```html
{{TEXT:nagłówek}}      → text input in UI
{{IMAGE:zdjęcie_główne}} → image upload + drag/zoom in UI
```

**Rules:**
- `label` is the field key and display name (displayed capitalized in UI)
- Regex: `/\{\{(TEXT|IMAGE):([^}]+)\}\}/g`
- Multiple `TEXT` and `IMAGE` placeholders allowed per template
- Placeholders may appear anywhere in the HTML (inside attributes, text nodes, etc.)

**Replacement at save time (frontend):**

- `{{TEXT:label}}` → raw string value typed by user
- `{{IMAGE:label}}` → `<img src="data:image/jpeg;base64,..." style="width:100%; height:100%; object-fit:cover; object-position:X% Y%; transform:scale(Z);" />`
  - `object-position` encodes pan state (normalized 0–100%)
  - `transform:scale()` encodes zoom state
  - Frontend resizes/compresses image to max 1920px / ~400KB before base64 encoding

---

## 2. User Flow

1. User clicks **Narzędzia → Stwórz obraz** in Topbar
2. Modal opens — user selects a template (dropdown or card list)
3. Modal switches to **split editor**:
   - **Left panel:** dynamically generated form fields — one per placeholder detected in template HTML
     - `TEXT` fields: labeled text inputs
     - `IMAGE` fields: upload zone; after upload shows thumbnail + "active" state
   - **Right panel:** live HTML preview rendered via `<iframe srcdoc="...">` or `innerHTML`, updates on every keystroke / image change
   - **Image drag/zoom (A2 interaction):** clicking an IMAGE field in the left panel activates that image slot in the preview. The preview shows a drag cursor + `+`/`−` zoom buttons overlaid on the image zone. User drags to pan, clicks `+`/`−` or scrolls to zoom. Preview updates live via CSS.
4. Below the form: **"Przypisz do artykułu"** dropdown (optional)
   - Lists all org's articles sorted newest first
   - Default: empty (no association)
5. User clicks **Zapisz**
   - Frontend assembles final HTML (all placeholders replaced)
   - `POST /api/v2/tools/image-creator/jobs` → receives `job_id`
   - Frontend opens SSE: `GET /api/v2/tools/image-creator/jobs/{job_id}/stream`
   - Modal shows spinner
6. When SSE delivers `{status: "done", url: "..."}`:
   - Modal shows rendered image (full width preview)
   - **Download** button + **Copy link** button
   - If article was selected: image appears in ArticleView under the article body

---

## 3. Architecture — Hybrid (Approach 3)

Frontend owns: template parsing, form rendering, live preview, final HTML assembly (base64 + CSS pan/zoom).  
Backend owns: htmltomedia API integration, SSE job management, article image persistence.

### Data flow

```
Frontend
  POST /api/v2/tools/image-creator/jobs  {html: "<filled HTML>", article_id?: "uuid"}
    ↓
Backend (tools/image_creator/service.py)
  POST htmltomedia /images  {html, width: 1200, format: "jpeg", callback_url: "/webhook"}
  Returns job_id to frontend
    ↓
Frontend opens SSE  GET /api/v2/tools/image-creator/jobs/{job_id}/stream
  (modal shows spinner)
    ↓
htmltomedia renders → POST /api/v2/tools/image-creator/webhook  {job_id, status, url}
Backend:
  - if article_id: appends {url, name, created_at} to article.generated_images
  - pushes event to asyncio.Queue[job_id]
    ↓
SSE delivers {status, url} to frontend
Frontend shows result in modal
```

---

## 4. Backend Module

**Location:** `tools/image_creator/` (self-contained, portable)

**External dependencies:** only `backend.auth.deps` (auth) and `backend.database` (DB session) from AW-v2.

### Files

| File | Responsibility |
|------|---------------|
| `config.py` | `HTML2MEDIA_BASE_URL`, `HTML2MEDIA_API_KEY` from env |
| `schemas.py` | `CreateJobRequest`, `CreateJobResponse`, `WebhookPayload`, `JobEvent` |
| `service.py` | `submit_job()`, `wait_for_result()` (SSE generator), `handle_webhook()`, `_queues` dict |
| `routes.py` | FastAPI router with 3 endpoints |

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v2/tools/image-creator/jobs` | JWT | Submit filled HTML, returns `{job_id}` |
| `GET` | `/api/v2/tools/image-creator/jobs/{job_id}/stream` | JWT | SSE stream — delivers result when webhook fires |
| `POST` | `/api/v2/tools/image-creator/webhook` | shared secret header | Callback from htmltomedia |

### New env vars

```
HTML2MEDIA_BASE_URL=https://headlinesforge.com/html2media
HTML2MEDIA_API_KEY=<key>
HTML2MEDIA_WEBHOOK_SECRET=<random string>  # validated in webhook handler
```

### `service.py` key structure

```python
_queues: dict[str, asyncio.Queue] = {}

async def submit_job(html: str, callback_url: str) -> str:
    """POST to htmltomedia, return job_id."""

async def wait_for_result(job_id: str) -> AsyncGenerator[str, None]:
    """Create queue, yield SSE events, clean up on disconnect."""

async def handle_webhook(job_id: str, status: str, url: str | None,
                         article_id: str | None, org_code: str, db) -> None:
    """Save URL to article if article_id set, push to queue."""
```

---

## 5. Database Changes

**One Alembic migration — two new columns:**

### `OrgConfig.image_templates`

```python
image_templates: list = Field(
    default_factory=list,
    sa_column=Column(JSONB, nullable=False, server_default=text("'[]'")),
)
# Element shape: {id: str, name: str, html: str}
# Same pattern as existing article_templates
```

### `Article.generated_images`

```python
generated_images: list[dict] = Field(
    default_factory=list,
    sa_column=Column(JSONB, nullable=False, server_default=text("'[]'")),
)
# Element shape: {url: str, name: str, created_at: ISO str}
```

No job persistence table needed — job_id is ephemeral (lives as long as the SSE connection).

> **Local dev note:** The webhook callback requires a publicly reachable URL. In local dev the webhook will never fire — the SSE stream will hang. Use ngrok or skip the image creator flow in local dev; the feature is designed for staging/production use.

---

## 6. Frontend Structure

**Location:** `frontend/src/tools/image-creator/`

| File | Responsibility |
|------|---------------|
| `ImageCreatorModal.tsx` | Modal shell, step management (template select → editor → result) |
| `TemplateSelector.tsx` | Dropdown / card list of org's image templates |
| `TemplateFiller.tsx` | Split layout: left form + right live preview |
| `PlaceholderForm.tsx` | Dynamically renders TEXT inputs and IMAGE upload slots from parsed placeholders |
| `LivePreview.tsx` | `<iframe srcdoc>` or `innerHTML` div, updated on every change |
| `DragZoomOverlay.tsx` | Drag-to-pan + scroll/button zoom overlay on active image slot in preview |
| `ResultPanel.tsx` | Shows generated image, Download button, Copy link button |
| `useImageCreatorJob.ts` | Submits job, manages SSE connection, returns `{status, url, error}` |
| `useImageTemplates.ts` | Fetches `image_templates` from org config |
| `htmlBuilder.ts` | `buildHtml(template, values, imageStates)` — assembles final HTML with base64 + CSS |
| `imagePrepare.ts` | Resizes + compresses uploaded image to base64 (max 1920px, ~400KB) |

### Topbar change

`Topbar.tsx` gets a new `ToolsMenu` component — a dropdown button "Narzędzia" that renders a menu with "Stwórz obraz" item. Clicking opens `ImageCreatorModal`.

### ArticleView change

`ArticleView.tsx` — if `article.generated_images.length > 0`, renders a "Grafiki" section below the article body. Each item: image thumbnail + Download + Copy link buttons.

---

## 7. Settings — "Szablony obrazków"

- New section ID `"szablony-obrazkow"` added to `SettingsNav` (after existing `"szablony"`)
- New section in `DomainConfigForm` — list of templates with:
  - Name input
  - HTML textarea (raw template HTML)
  - Add / Delete buttons
- CRUD is local state, saved on "Zapisz ustawienia" like all other settings fields

---

## 8. Htmltomedia API integration

**Submit job:**
```http
POST https://headlinesforge.com/html2media/images
Authorization: Bearer <HTML2MEDIA_API_KEY>
Content-Type: application/json

{"html": "<filled HTML>", "width": 1200, "format": "jpeg", "callback_url": "https://headlinesforge.com/api/v2/tools/image-creator/webhook"}
```

**Webhook payload received:**
```json
{"job_id": "uuid", "status": "done", "url": "https://pub-xxx.r2.dev/uuid/result.jpg", "error": null}
```

---

## 9. What We Don't Store

- Raw uploaded images (base64 only in-memory on frontend, never persisted)
- Job records (ephemeral, in-memory queue only)
- Generated image files (htmltomedia's R2 owns those)
- Unassigned image URLs (if user didn't select an article, URL is lost after modal closes)
