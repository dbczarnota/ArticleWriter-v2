# Contact Form Backend — Design Spec

**Date:** 2026-05-13
**Status:** Approved

## Goal

Replace the broken Formspree integration in the landing page contact form with a backend FastAPI endpoint that sends e-mail via Resend.

## Problem

`LandingContact.tsx` posts to `https://formspree.io/hello@headlinesforge.com` — the legacy email-based Formspree URL format is deprecated and returns an error on submission.

## Architecture

A single public FastAPI endpoint `POST /v2/contact` receives form data and calls the Resend API to deliver the message to `hello@headlinesforge.com`. The frontend switches its fetch target from Formspree to this endpoint.

No authentication is required — the endpoint is intentionally public (landing page visitors are unauthenticated).

## Backend

### Endpoint

```
POST /v2/contact
```

- **Auth:** none (no `Depends(get_current_user)`)
- **Request body** (JSON, Pydantic model `ContactRequest`):
  - `name: str` — required, 1–200 chars
  - `email: EmailStr` — required
  - `company: str | None` — optional
  - `message: str` — required, 1–4000 chars
- **Response:** `200 {"ok": true}` on success
- **Errors:** `422` on validation failure, `500` if Resend call fails

### Email

- **Library:** `resend` (PyPI: `resend`)
- **From:** `noreply@headlinesforge.com`
- **To:** `hello@headlinesforge.com`
- **Reply-To:** submitter's `email`
- **Subject:** `[HeadlinesForge] Wiadomość od {name}`
- **Body (plain text):**
  ```
  Od: {name} <{email}>
  Firma: {company or "—"}

  {message}
  ```

### Config

- New env var: `RESEND_API_KEY`
- Read via `os.environ.get("RESEND_API_KEY")` in the endpoint (consistent with how other keys are read in this project — no `.env` loading)
- If key is absent, endpoint returns `503` with a clear message (dev safety net)

### Placement

Added to `backend/api/v2.py` alongside other public endpoints. `ContactRequest` Pydantic model added to `backend/api/schemas.py`.

## Frontend

`LandingContact.tsx`:
- Remove `FORMSPREE_ENDPOINT` constant
- Replace fetch URL with `/api/v2/contact` (goes through the existing Vite `/api` proxy to `http://localhost:8000` in dev, and hits the backend directly in prod via the same proxy config)
- Send `Content-Type: application/json` with `JSON.stringify({name, email, company, message})` instead of `FormData`
- Read field values via `useRef` or controlled state — switch from uncontrolled `FormData` to controlled inputs

## Infrastructure

- `RESEND_API_KEY` added to k8s secret `headlinesforge-secrets` (same pattern as `GEMINI_API_KEY` etc.)
- Resend domain verification: `headlinesforge.com` needs SPF/DKIM DNS records added in Resend dashboard before `noreply@headlinesforge.com` can send

## Rate Limiting

None on this endpoint for now. Resend's free tier (3k emails/month) acts as a natural cap. Revisit if spam becomes an issue.
