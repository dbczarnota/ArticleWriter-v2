# Image Creator — Deploy Checklist

End-to-end checklist for shipping the Image Creator tool to production.

## Pre-deploy

### k8s secrets (Rancher)

In `headlinesforge-secrets`, ensure this key exists:

| Key | Value | Purpose |
|-----|-------|---------|
| `HTML2MEDIA_ADMIN_SECRET` | (same admin secret as configured on htmltomedia service) | Used by `service.enable_org` to mint per-org API keys |

In `k8s/backend-deploy.yaml` the env var is already wired (`HTML2MEDIA_ADMIN_SECRET` → `secretKeyRef: headlinesforge-secrets / HTML2MEDIA_ADMIN_SECRET`).

**No HTML2MEDIA_WEBHOOK_SECRET is needed.** Webhook authentication uses per-job nonces in the callback URL, generated at submit time. Zero shared secret means htmltomedia needs no changes.

### Database

Migration `b0c1d2e3f4a5` adds `image_creator_enabled` (bool) and `image_creator_api_key` (string) columns to `org_configs`. Runs automatically via the `migrate` initContainer on every backend deploy.

## Deploy

```
gh workflow run "Build & Deploy" --ref master
```

(Standard `Build & Deploy` workflow. The initContainer applies pending migrations before the backend pod starts serving, so the API never serves on a stale schema.)

## Post-deploy smoke test

For each org that should have Image Creator enabled:

1. **Sign in to ArticleWriter** with a user belonging to the target org.
2. **Settings → Szablony obrazków**
3. Click **Włącz**.
   - First time: the backend calls `htmltomedia POST /keys` with `X-Admin-Key`, stores the returned key in `org_configs.image_creator_api_key`, and sets `image_creator_enabled=true`. Idempotent: re-enabling later just flips the flag.
   - If htmltomedia returns 4xx/5xx: the UI shows the error and the org stays disabled.
4. Add a test template:
   - Name: "Test"
   - HTML: `<div style="width:600px;height:400px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;font-size:42px;display:flex;align-items:center;justify-content:center;font-family:sans-serif">{{TEXT:title}}</div>`
5. Click **Save**.
6. **Top bar → Narzędzia → Stwórz obraz**.
7. Select "Test" template, type a title, click **Generuj obraz**.
8. Expected: SSE waits, htmltomedia renders, image URL is returned, preview shown.
9. If associated with an article, the generated image appears in the article view (`generated_images` section).

### Verifying in the DB

```sql
SELECT org_code, image_creator_enabled,
       LENGTH(image_creator_api_key) AS key_len,
       jsonb_array_length(image_templates) AS template_count
FROM org_configs
WHERE org_code = '<org-code>';
```

`key_len` should be > 0 once the toggle has been activated at least once.

### Verifying in Logfire

Search spans by `http.target` for `tools/image-creator/jobs`. Each successful job:

1. `POST /v2/tools/image-creator/enable` (first time only)
2. `POST /v2/tools/image-creator/jobs` (200)
3. `GET /v2/tools/image-creator/jobs/<job_id>/stream` (200, ~30 s long)
4. `POST /v2/tools/image-creator/webhook?nonce=…` (200)

If step 4 returns 401, the nonce check failed — investigate whether htmltomedia is preserving the callback URL query params.

## Rollback

If something breaks after deploy:

```
kubectl set image deploy/backend backend=ghcr.io/dbczarnota/articlewriter-v2/backend:<previous-tag> -n headlinesforge
```

Migration is forward-only here (adds nullable columns + a bool with `server_default=false`), so rolling back the image is safe — the new columns are simply ignored by the old code.

## Known limitations to monitor

- **In-memory `_jobs` dict.** Webhook delivery is tied to the pod that submitted the job. Scaling backend deployment beyond 1 replica will cause jobs to "lose" their webhook (the webhook hits one pod, the SSE stream is on another). Plan to address before scaling — see `tools/image_creator/service.py:_jobs` for the registry that needs to move to Redis or a DB-backed pub/sub.
- **No rate limiting** on `POST /jobs`. A compromised user account could enqueue unbounded jobs. Add per-org rate limiting before exposing to untrusted users.
- **Template HTML is rendered server-side by htmltomedia** as a real browser. Templates are admin-set via Settings, so a malicious admin could exfiltrate via outbound requests in the template. Acceptable for trusted-admin scenarios; lock down before allowing untrusted admins.
