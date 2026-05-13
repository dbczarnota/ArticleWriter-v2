# Contact Form Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken Formspree integration with a FastAPI `POST /v2/contact` endpoint that sends email via Resend API, and update the landing page form to use it.

**Architecture:** A public (no-auth) FastAPI endpoint validates the form payload with Pydantic, then calls the Resend REST API via `httpx.AsyncClient`. The frontend switches from `FormData`/Formspree to `JSON`/`/v2/contact`. No new Python dependency needed — `httpx` is already available transitively via `logfire[httpx]`.

**Tech Stack:** FastAPI, Pydantic v2, httpx (async), respx (test mocking), React 18 + TypeScript

---

## File Map

| File | Change |
|------|--------|
| `backend/api/schemas.py` | Add `ContactRequest` Pydantic model |
| `backend/api/v2.py` | Add `POST /v2/contact` endpoint |
| `tests/backend/test_contact_endpoint.py` | New — tests for the endpoint |
| `frontend/src/components/landing/LandingContact.tsx` | Switch to controlled state + POST JSON to `/v2/contact` |

---

### Task 1: ContactRequest schema

**Files:**
- Modify: `backend/api/schemas.py` (append at end)

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_contact_endpoint.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


def test_contact_missing_fields(client):
    res = client.post("/v2/contact", json={})
    assert res.status_code == 422


def test_contact_invalid_email(client):
    res = client.post("/v2/contact", json={
        "name": "Test",
        "email": "not-an-email",
        "message": "Hello",
    })
    assert res.status_code == 422


def test_contact_name_too_long(client):
    res = client.post("/v2/contact", json={
        "name": "x" * 201,
        "email": "test@example.com",
        "message": "Hello",
    })
    assert res.status_code == 422


def test_contact_message_too_long(client):
    res = client.post("/v2/contact", json={
        "name": "Test",
        "email": "test@example.com",
        "message": "x" * 4001,
    })
    assert res.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backend/test_contact_endpoint.py -v
```

Expected: ImportError or 404 (endpoint doesn't exist yet).

- [ ] **Step 3: Add ContactRequest to schemas.py**

Append to the end of `backend/api/schemas.py`:

```python
from pydantic import EmailStr


class ContactRequest(BaseModel):
    name: str = PydanticField(min_length=1, max_length=200)
    email: EmailStr
    company: str | None = PydanticField(default=None, max_length=200)
    message: str = PydanticField(min_length=1, max_length=4000)
```

Note: `PydanticField` is already imported as `from pydantic import Field as PydanticField` at the top of schemas.py. `EmailStr` needs a new import — add it to the existing pydantic import line:

```python
from pydantic import BaseModel, EmailStr, field_validator
from pydantic import Field as PydanticField
```

- [ ] **Step 4: Run tests — schema validation tests should now pass**

```
pytest tests/backend/test_contact_endpoint.py::test_contact_missing_fields tests/backend/test_contact_endpoint.py::test_contact_invalid_email tests/backend/test_contact_endpoint.py::test_contact_name_too_long tests/backend/test_contact_endpoint.py::test_contact_message_too_long -v
```

Expected: 4 × PASS (validation tests pass once schema exists, even before the endpoint).

- [ ] **Step 5: Commit**

```bash
git add backend/api/schemas.py tests/backend/test_contact_endpoint.py
git commit -m "feat(contact): add ContactRequest schema + validation tests"
```

---

### Task 2: POST /v2/contact endpoint

**Files:**
- Modify: `backend/api/v2.py` (add endpoint near top, after imports)

- [ ] **Step 1: Write the failing integration test**

Add to `tests/backend/test_contact_endpoint.py`:

```python
import respx
import httpx as _httpx


@respx.mock
def test_contact_success(client):
    respx.post("https://api.resend.com/emails").mock(
        return_value=_httpx.Response(200, json={"id": "fake-id"})
    )
    import os
    os.environ["RESEND_API_KEY"] = "test-key"

    res = client.post("/v2/contact", json={
        "name": "Jan Kowalski",
        "email": "jan@example.com",
        "company": "ACME",
        "message": "Chcę demo.",
    })
    assert res.status_code == 200
    assert res.json() == {"ok": True}


@respx.mock
def test_contact_no_api_key(client):
    import os
    os.environ.pop("RESEND_API_KEY", None)

    res = client.post("/v2/contact", json={
        "name": "Jan",
        "email": "jan@example.com",
        "message": "Test",
    })
    assert res.status_code == 503


@respx.mock
def test_contact_resend_failure(client):
    respx.post("https://api.resend.com/emails").mock(
        return_value=_httpx.Response(500, json={"error": "server error"})
    )
    import os
    os.environ["RESEND_API_KEY"] = "test-key"

    res = client.post("/v2/contact", json={
        "name": "Jan",
        "email": "jan@example.com",
        "message": "Test",
    })
    assert res.status_code == 500
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/backend/test_contact_endpoint.py::test_contact_success tests/backend/test_contact_endpoint.py::test_contact_no_api_key tests/backend/test_contact_endpoint.py::test_contact_resend_failure -v
```

Expected: FAIL — 404 (endpoint not yet defined).

- [ ] **Step 3: Add the endpoint to v2.py**

In `backend/api/v2.py`, add these imports at the top (with the other imports):

```python
import httpx
import os
```

Then add the endpoint. A good place is right after the `router = APIRouter(prefix="/v2")` line (around line 50), before the first `@router.post`:

```python
@router.post("/contact")
async def contact(req: ContactRequest) -> dict:
    """Public endpoint — no auth required. Sends contact form to hello@headlinesforge.com via Resend."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Email service not configured")

    body_text = (
        f"Od: {req.name} <{req.email}>\n"
        f"Firma: {req.company or '—'}\n\n"
        f"{req.message}"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "noreply@headlinesforge.com",
                "to": ["hello@headlinesforge.com"],
                "reply_to": [req.email],
                "subject": f"[HeadlinesForge] Wiadomość od {req.name}",
                "text": body_text,
            },
            timeout=10.0,
        )

    if not response.is_success:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to send email")

    return {"ok": True}
```

Also add `ContactRequest` to the imports from schemas at the top of `v2.py`. Find the existing import line that looks like:

```python
from backend.api.schemas import (
    ArticleRequest,
    ...
)
```

And add `ContactRequest` to it.

- [ ] **Step 4: Run all contact tests**

```
pytest tests/backend/test_contact_endpoint.py -v
```

Expected: 7 × PASS.

- [ ] **Step 5: Run full backend test suite to check for regressions**

```
pytest tests/ -x -q
```

Expected: all pass (or pre-existing failures only — none introduced by this change).

- [ ] **Step 6: Lint + type check**

```
ruff check backend/api/v2.py backend/api/schemas.py
ruff format --check backend/api/v2.py backend/api/schemas.py
pyright backend/api/v2.py backend/api/schemas.py
```

Expected: no new errors.

- [ ] **Step 7: Commit**

```bash
git add backend/api/v2.py backend/api/schemas.py tests/backend/test_contact_endpoint.py
git commit -m "feat(contact): POST /v2/contact endpoint via Resend"
```

---

### Task 3: Update LandingContact.tsx

**Files:**
- Modify: `frontend/src/components/landing/LandingContact.tsx`

- [ ] **Step 1: Replace the component**

Replace the entire content of `frontend/src/components/landing/LandingContact.tsx` with the version below. Key changes:
- Remove `FORMSPREE_ENDPOINT`
- Add controlled state for each field (`name`, `email`, `company`, `message`)
- POST JSON to `/v2/contact` (proxied to backend by Vite in dev, direct in prod)

```tsx
import { useState } from "react";
import { useT } from "../../i18n";

type Status = "idle" | "submitting" | "success" | "error";

export function LandingContact() {
  const t = useT();
  const c = t.landing.contact;
  const [status, setStatus] = useState<Status>("idle");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    try {
      const res = await fetch("/v2/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, company: company || undefined, message }),
      });
      setStatus(res.ok ? "success" : "error");
    } catch {
      setStatus("error");
    }
  }

  return (
    <section id="contact" className="landing-contact">
      <div className="landing-container">
        <div className="landing-contact-inner">
          <div className="landing-contact-info">
            <div className="landing-label-tag">{c.tag}</div>
            <h2 className="landing-section-h landing-on-dark-h">{c.h}</h2>
            <p className="landing-section-sub landing-on-dark-sub">{c.sub}</p>
            <div className="landing-contact-info-row">
              <div className="landing-contact-info-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                </svg>
              </div>
              <div>
                <div className="landing-contact-info-label">E-mail</div>
                <div className="landing-contact-info-value">{c.infoEmail}</div>
              </div>
            </div>
            <div className="landing-contact-info-row">
              <div className="landing-contact-info-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 10a5 5 0 0 1-5 5"/><path d="M3 10a9 9 0 0 0 9 9"/><path d="M21 10a9 9 0 0 0-9-9"/><circle cx="12" cy="10" r="3"/>
                </svg>
              </div>
              <div>
                <div className="landing-contact-info-label">Demo</div>
                <div className="landing-contact-info-value">{c.infoDemo}</div>
              </div>
            </div>
          </div>

          <div className="landing-contact-form">
            {status === "success" ? (
              <div className="landing-contact-success">
                <div style={{ fontSize: 40, marginBottom: 16 }}>✓</div>
                <div className="landing-contact-success-h">{c.successH}</div>
                <div className="landing-contact-success-p">{c.successP}</div>
              </div>
            ) : (
              <form onSubmit={handleSubmit}>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelName}</label>
                  <input
                    type="text"
                    required
                    className="landing-contact-input"
                    placeholder={c.placeholderName}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelEmail}</label>
                  <input
                    type="email"
                    required
                    className="landing-contact-input"
                    placeholder={c.placeholderEmail}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelCompany}</label>
                  <input
                    type="text"
                    className="landing-contact-input"
                    placeholder={c.placeholderCompany}
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                  />
                </div>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelMessage}</label>
                  <textarea
                    required
                    className="landing-contact-textarea"
                    placeholder={c.placeholderMessage}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="landing-contact-submit"
                  disabled={status === "submitting"}
                >
                  {status === "submitting" ? c.submitting : c.submit}
                </button>
                {status === "error" && (
                  <div className="landing-contact-error">{c.errorP}</div>
                )}
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: TypeScript check**

```
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/landing/LandingContact.tsx
git commit -m "feat(contact): switch landing form to /v2/contact endpoint"
```

---

### Task 4: Push + infrastructure note

- [ ] **Step 1: Push to master**

```bash
git push origin master
```

- [ ] **Step 2: Add RESEND_API_KEY to k8s secret**

Once you have the Resend API key, add it to the k8s secret:

```bash
export KUBECONFIG=C:\Users\czarn\.kube\headlinesforge.yaml
kubectl edit secret headlinesforge-secrets -n headlinesforge
```

Add `RESEND_API_KEY: <base64-encoded-key>` under `data`. To base64-encode: `echo -n "re_xxxx" | base64`

- [ ] **Step 3: Verify Resend domain**

In the Resend dashboard, add domain `headlinesforge.com` and add the provided DNS records (TXT for SPF, CNAME for DKIM). Without this, emails from `noreply@headlinesforge.com` will be rejected.

- [ ] **Step 4: Deploy**

```bash
gh workflow run "Build & Deploy" --ref master
```
