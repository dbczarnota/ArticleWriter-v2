# Streams UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose stream subscriptions in the app — a "Streamy" settings section for CRUD, and two new tabs in the Discovery Hub ("Streamy" stats, "Tematy streamów" topics).

**Architecture:** All stream-specific code lives in dedicated files (prefixed `Streams`/`useStream`); existing files get only minimal wiring additions. `DiscoveryHub` gains two tabs that lazy-import stream components. `SettingsView` branches on `activeSection === "streamy"` to render `StreamsConfigSection` instead of `DomainConfigForm`, so `DomainConfigForm` is never touched. This makes the feature trivially removable.

**Tech Stack:** React + TypeScript + Vite, custom `useApi` hook, Python/FastAPI backend, SQLModel, pytest, vitest.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `backend/api/streams.py` | Add `GET /v2/streams/topics` endpoint |
| Modify | `frontend/src/types.ts` | Add `StreamSubscription`, `StreamTopic` interfaces |
| Modify | `frontend/src/i18n/types.ts` | Add `streams` namespace + `settingsNav.streams` |
| Modify | `frontend/src/i18n/en.ts` | English stream strings |
| Modify | `frontend/src/i18n/pl.ts` | Polish stream strings |
| Modify | `frontend/src/components/ui/icons.tsx` | Add `StreamsIcon`, `StreamTopicsIcon` |
| Create | `frontend/src/lib/useStreamSubscriptions.ts` | CRUD + 30 s poll for subscriptions |
| Create | `frontend/src/lib/useStreamTopics.ts` | Fetch stream topics, 30 s poll |
| Create | `frontend/src/components/StreamsHealth.tsx` | Subscription status cards (mirrors FeedsHealth) |
| Create | `frontend/src/components/StreamTopicsList.tsx` | Discovered topics list (mirrors ItemsTable) |
| Create | `frontend/src/components/StreamsConfigSection.tsx` | Settings form: add/delete subscriptions |
| Modify | `frontend/src/components/DiscoveryHub.tsx` | Add 2 tabs: "Streamy" + "Tematy streamów" |
| Modify | `frontend/src/components/SettingsNav.tsx` | Add "streamy" to `SECTION_IDS` |
| Modify | `frontend/src/components/SettingsView.tsx` | Branch to `StreamsConfigSection` for "streamy" |

---

### Task 1: Backend — `GET /v2/streams/topics`

**Files:**
- Modify: `backend/api/streams.py`
- Modify: `tests/backend/test_streams_api.py`

Context: `StreamTopic` is in `backend/db/models.py`. `StreamSubscription.org_code` links topics to an org. The null-DB path returns `[]` (same pattern as every other endpoint in this file).

- [ ] **Step 1: Write failing test**

Add to `tests/backend/test_streams_api.py` (find the existing `ORG_HEADERS` constant and `client` fixture at the top of that file):

```python
def test_list_stream_topics_null_backend(client):
    resp = client.get("/v2/streams/topics", headers=ORG_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run to verify it fails**

```
uv run pytest tests/backend/test_streams_api.py::test_list_stream_topics_null_backend -v
```

Expected: FAIL — `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Add endpoint to `backend/api/streams.py`**

Add after the existing `get_digests` route (after line 266, before the end of the file):

```python
@router.get("/topics")
async def list_stream_topics(
    org: Org = Depends(get_current_org),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    if get_db_backend() != "postgres":
        return []
    sm = get_session_maker()
    async with sm() as session:  # type: ignore[union-attr]
        sub_result = await session.execute(
            select(StreamSubscription).where(StreamSubscription.org_code == org.code)  # type: ignore[arg-type]
        )
        sub_ids = [s.id for s in sub_result.scalars().all()]
        if not sub_ids:
            return []
        from backend.db.models import StreamTopic

        topic_result = await session.execute(
            select(StreamTopic)
            .where(StreamTopic.subscription_id.in_(sub_ids))  # type: ignore[arg-type]
            .order_by(StreamTopic.last_seen_at.desc())  # type: ignore[arg-type]
            .limit(limit)
        )
        topics = topic_result.scalars().all()
        return [
            {
                "topic_id": str(t.id),
                "subscription_id": str(t.subscription_id),
                "title": t.title,
                "is_news": t.is_news,
                "summary": t.summary,
                "speakers": t.speakers,
                "facts": t.facts,
                "quotes": t.quotes,
                "first_seen_at": t.first_seen_at.isoformat(),
                "last_seen_at": t.last_seen_at.isoformat(),
                "window_start_seconds": t.window_start_seconds,
                "window_end_seconds": t.window_end_seconds,
            }
            for t in topics
        ]
```

- [ ] **Step 4: Run lint + types + test**

```
uv run ruff check backend/api/streams.py && uv run pyright backend/api/streams.py && uv run pytest tests/backend/test_streams_api.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```
git add backend/api/streams.py tests/backend/test_streams_api.py
git commit -m "feat(streams): GET /v2/streams/topics endpoint"
```

---

### Task 2: Frontend Types

**Files:**
- Modify: `frontend/src/types.ts` (append at end)

- [ ] **Step 1: Add types**

Append to the end of `frontend/src/types.ts`:

```typescript
export interface StreamSubscription {
  id: string;
  org_code: string;
  name: string;
  stream_url: string;
  stream_type: string;
  url_refresh_url: string | null;
  url_refresh_field: string;
  status: "active" | "stopped" | "paused";
  chunk_duration_seconds: number;
  created_at: string;
  started_at: string | null;
  stopped_at: string | null;
}

export interface StreamTopic {
  topic_id: string;
  subscription_id: string;
  title: string;
  is_news: boolean;
  summary: string;
  speakers: Array<{ name_or_role: string; description?: string }>;
  facts: Array<{ text: string; speaker?: string }>;
  quotes: Array<{ text: string; speaker?: string }>;
  first_seen_at: string;
  last_seen_at: string;
  window_start_seconds: number;
  window_end_seconds: number;
}
```

- [ ] **Step 2: Type-check**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/types.ts
git commit -m "feat(streams): StreamSubscription + StreamTopic TypeScript interfaces"
```

---

### Task 3: i18n

**Files:**
- Modify: `frontend/src/i18n/types.ts`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/pl.ts`

- [ ] **Step 1: Extend `Translations` interface**

In `frontend/src/i18n/types.ts`:

1. In the `settingsNav` block (after `discovery: string;`), add:
```typescript
    streams: string;
```

2. After the closing `};` of the `newArticle` block (at the end of the interface, before the closing `}`), add:
```typescript
  streams: {
    views: {
      subscriptions: string;
      topics: string;
    };
    subscription: {
      live: string;
      stopped: string;
      paused: string;
      noStreams: string;
      streamType: string;
      chunkDuration: string;
      delete: string;
      confirmDelete: string;
      lastStarted: string;
    };
    topic: {
      loading: string;
      noTopics: string;
      newsBadge: string;
      notNewsBadge: string;
      lastSeen: string;
    };
    config: {
      sectionStreams: string;
      streamsHint: string;
      addStream: string;
      removeStream: string;
      streamName: string;
      streamNamePlaceholder: string;
      streamUrl: string;
      streamUrlPlaceholder: string;
      streamType: string;
      streamTypePlaceholder: string;
      urlRefreshUrl: string;
      urlRefreshUrlPlaceholder: string;
      urlRefreshField: string;
      chunkDuration: string;
      saving: string;
      saved: string;
    };
  };
```

- [ ] **Step 2: Add English strings**

In `frontend/src/i18n/en.ts`, in the `settingsNav` object after `discovery: "Discovery (RSS topic discovery)",`, add:
```typescript
    streams: "Streams",
```

Then after the `newArticle` object's closing `},`, add:
```typescript
  streams: {
    views: {
      subscriptions: "Streams",
      topics: "Stream Topics",
    },
    subscription: {
      live: "Live",
      stopped: "Stopped",
      paused: "Paused",
      noStreams: "No streams configured. Add one below.",
      streamType: "Type",
      chunkDuration: "Chunk",
      delete: "Delete",
      confirmDelete: "Delete this stream?",
      lastStarted: "Started",
    },
    topic: {
      loading: "Loading topics…",
      noTopics: "No topics discovered yet. Start a stream subscription first.",
      newsBadge: "News",
      notNewsBadge: "Non-news",
      lastSeen: "Last seen",
    },
    config: {
      sectionStreams: "Audio Streams",
      streamsHint: "Subscribe to live radio or TV audio streams. The pipeline chunks the audio, transcribes it, and extracts topics automatically.",
      addStream: "Add stream",
      removeStream: "Remove",
      streamName: "Name",
      streamNamePlaceholder: "e.g. TVP Info",
      streamUrl: "Stream URL",
      streamUrlPlaceholder: "https://... or http://...",
      streamType: "Type (radio / tv)",
      streamTypePlaceholder: "radio",
      urlRefreshUrl: "URL refresh endpoint (optional)",
      urlRefreshUrlPlaceholder: "https://api.example.com/stream-url",
      urlRefreshField: "JSON field for URL",
      chunkDuration: "Chunk duration (seconds)",
      saving: "Saving…",
      saved: "Saved",
    },
  },
```

- [ ] **Step 3: Add Polish strings**

In `frontend/src/i18n/pl.ts`, in the `settingsNav` object after `discovery: "Odkrywanie (tematy z RSS)",`, add:
```typescript
    streams: "Streamy",
```

Then after the `newArticle` object's closing `},`, add:
```typescript
  streams: {
    views: {
      subscriptions: "Streamy",
      topics: "Tematy ze streamów",
    },
    subscription: {
      live: "Live",
      stopped: "Zatrzymany",
      paused: "Wstrzymany",
      noStreams: "Brak skonfigurowanych streamów. Dodaj poniżej.",
      streamType: "Typ",
      chunkDuration: "Chunk",
      delete: "Usuń",
      confirmDelete: "Usunąć ten stream?",
      lastStarted: "Uruchomiony",
    },
    topic: {
      loading: "Ładowanie tematów…",
      noTopics: "Brak odkrytych tematów. Najpierw uruchom subskrypcję streamu.",
      newsBadge: "News",
      notNewsBadge: "Nie-news",
      lastSeen: "Ostatnio widziano",
    },
    config: {
      sectionStreams: "Streamy audio",
      streamsHint: "Subskrybuj live'owe streamy radiowe lub telewizyjne. Pipeline dzieli audio na chunki, transkrybuje i automatycznie wyciąga tematy.",
      addStream: "Dodaj stream",
      removeStream: "Usuń",
      streamName: "Nazwa",
      streamNamePlaceholder: "np. TVP Info",
      streamUrl: "URL streamu",
      streamUrlPlaceholder: "https://... lub http://...",
      streamType: "Typ (radio / tv)",
      streamTypePlaceholder: "radio",
      urlRefreshUrl: "Endpoint odświeżania URL (opcjonalnie)",
      urlRefreshUrlPlaceholder: "https://api.example.com/stream-url",
      urlRefreshField: "Pole JSON z URL",
      chunkDuration: "Czas chunka (sekundy)",
      saving: "Zapisywanie…",
      saved: "Zapisano",
    },
  },
```

- [ ] **Step 4: Type-check**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors (TypeScript will catch any missing keys).

- [ ] **Step 5: Commit**

```
git add frontend/src/i18n/types.ts frontend/src/i18n/en.ts frontend/src/i18n/pl.ts
git commit -m "feat(streams): i18n strings for streams UI (en + pl)"
```

---

### Task 4: Icons

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx`

The existing pattern: every icon is an exported function returning `<svg {...baseProps} {...props}>`. `baseProps` is already defined at the top of the file. Use `currentColor` — no hardcoded colors.

- [ ] **Step 1: Add two icons**

Append at the end of `frontend/src/components/ui/icons.tsx`:

```typescript
export function StreamsIcon(props: SVGProps<SVGSVGElement>) {
  // Radio tower / broadcast icon
  return (
    <svg {...baseProps} {...props}>
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <circle cx="12" cy="20" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function StreamTopicsIcon(props: SVGProps<SVGSVGElement>) {
  // List with a pulse line — topics from audio
  return (
    <svg {...baseProps} {...props}>
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <polyline points="3 6 4 7 5 6" />
      <polyline points="3 12 4 13 5 12" />
      <polyline points="3 18 4 19 5 18" />
    </svg>
  );
}
```

- [ ] **Step 2: Type-check + test**

```
cd frontend && npx tsc --noEmit && npm test
```

Expected: 0 errors, tests pass.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/ui/icons.tsx
git commit -m "feat(streams): StreamsIcon + StreamTopicsIcon"
```

---

### Task 5: `useStreamSubscriptions` hook

**Files:**
- Create: `frontend/src/lib/useStreamSubscriptions.ts`

Mirror `useDiscoveryFeeds.ts` exactly: `useApi`, `authReady`, 30 s poll, `refresh()` returned. Add `create` and `remove` for CRUD (no equivalent in feeds).

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/lib/useStreamSubscriptions.ts
import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { StreamSubscription } from "../types";

const POLL_MS = 30_000;

export function useStreamSubscriptions() {
  const { request, authReady } = useApi();
  const [subscriptions, setSubscriptions] = useState<StreamSubscription[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const rows = await request<StreamSubscription[]>("/v2/streams/subscriptions");
      setSubscriptions(rows);
    } catch (err) {
      console.error("useStreamSubscriptions: request failed", err);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (!authReady) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [authReady, refresh]);

  const create = useCallback(
    async (body: {
      name: string;
      stream_url: string;
      stream_type: string;
      url_refresh_url?: string;
      url_refresh_field?: string;
      chunk_duration_seconds?: number;
    }) => {
      const sub = await request<StreamSubscription>("/v2/streams/subscriptions", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await refresh();
      return sub;
    },
    [request, refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await request(`/v2/streams/subscriptions/${id}`, { method: "DELETE" });
      await refresh();
    },
    [request, refresh],
  );

  return { subscriptions, loading, refresh, create, remove };
}
```

- [ ] **Step 2: Type-check**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/lib/useStreamSubscriptions.ts
git commit -m "feat(streams): useStreamSubscriptions hook (CRUD + 30s poll)"
```

---

### Task 6: `useStreamTopics` hook

**Files:**
- Create: `frontend/src/lib/useStreamTopics.ts`

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/lib/useStreamTopics.ts
import { useCallback, useEffect, useState } from "react";
import { useApi } from "./useApi";
import type { StreamTopic } from "../types";

const POLL_MS = 30_000;

export function useStreamTopics() {
  const { request, authReady } = useApi();
  const [topics, setTopics] = useState<StreamTopic[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const rows = await request<StreamTopic[]>("/v2/streams/topics");
      setTopics(rows);
    } catch (err) {
      console.error("useStreamTopics: request failed", err);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (!authReady) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [authReady, refresh]);

  return { topics, loading, refresh };
}
```

- [ ] **Step 2: Type-check**

```
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/lib/useStreamTopics.ts
git commit -m "feat(streams): useStreamTopics hook (30s poll)"
```

---

### Task 7: `StreamsHealth` component

**Files:**
- Create: `frontend/src/components/StreamsHealth.tsx`

Mirrors `FeedsHealth.tsx`: card grid, status badge, `relTime` helper, delete button. The status badge mirrors FeedsHealth's `statusOf` pattern using the same CSS variables.

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/components/StreamsHealth.tsx
import type { StreamSubscription } from "../types";
import { StatusMessage } from "./ui/StatusMessage";
import { useT } from "../i18n";
import type { Translations } from "../i18n";

interface Props {
  subscriptions: StreamSubscription[];
  loading: boolean;
  onDelete: (id: string) => Promise<void>;
}

function relTime(iso: string | null, t: Translations): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return t.discovery.feed.justNow;
  if (min < 60) return `${min} ${t.discovery.feed.minAgo}`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}${t.discovery.feed.hAgo}`;
  return `${Math.round(h / 24)}${t.discovery.feed.dAgo}`;
}

function statusBadge(
  status: StreamSubscription["status"],
  t: Translations,
): { label: string; bg: string; fg: string } {
  if (status === "active")
    return { label: t.streams.subscription.live, bg: "var(--success-lt)", fg: "var(--success-fg)" };
  if (status === "paused")
    return { label: t.streams.subscription.paused, bg: "var(--warning-lt)", fg: "var(--warning-fg)" };
  return { label: t.streams.subscription.stopped, bg: "var(--error-lt)", fg: "var(--error-fg)" };
}

export function StreamsHealth({ subscriptions, loading, onDelete }: Props) {
  const t = useT();

  if (loading) return <StatusMessage kind="loading">{t.streams.topic.loading}</StatusMessage>;
  if (subscriptions.length === 0)
    return <StatusMessage kind="empty">{t.streams.subscription.noStreams}</StatusMessage>;

  return (
    <div
      style={{
        padding: 24,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
        gap: 16,
      }}
    >
      {subscriptions.map((sub) => {
        const badge = statusBadge(sub.status, t);
        return (
          <div
            key={sub.id}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: 16,
              background: "var(--white)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, color: "var(--text)" }}>{sub.name}</div>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    fontFamily: "ui-monospace, Menlo, monospace",
                    wordBreak: "break-all",
                  }}
                >
                  {sub.stream_url}
                </div>
              </div>
              <span
                style={{
                  color: badge.fg,
                  background: badge.bg,
                  fontSize: 12,
                  padding: "2px 8px",
                  borderRadius: 999,
                  flexShrink: 0,
                  alignSelf: "flex-start",
                  whiteSpace: "nowrap",
                }}
              >
                {badge.label}
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 12,
                fontSize: 14,
              }}
            >
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.streams.subscription.streamType}</div>
                <div style={{ fontWeight: 500, color: "var(--text)", textTransform: "uppercase" }}>
                  {sub.stream_type}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.streams.subscription.chunkDuration}</div>
                <div style={{ fontWeight: 500, color: "var(--text)" }}>{sub.chunk_duration_seconds}s</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>{t.streams.subscription.lastStarted}</div>
                <div style={{ fontWeight: 500, color: "var(--text)" }}>
                  {relTime(sub.started_at, t)}
                </div>
              </div>
            </div>
            <div style={{ marginTop: 12, display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(t.streams.subscription.confirmDelete)) {
                    void onDelete(sub.id);
                  }
                }}
                style={{
                  fontSize: 12,
                  color: "var(--error-fg)",
                  background: "none",
                  border: "1px solid var(--error-fg)",
                  borderRadius: "var(--radius)",
                  padding: "3px 10px",
                  cursor: "pointer",
                }}
              >
                {t.streams.subscription.delete}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Type-check + test**

```
cd frontend && npx tsc --noEmit && npm test
```

Expected: 0 errors, tests pass.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/StreamsHealth.tsx
git commit -m "feat(streams): StreamsHealth component — subscription status cards"
```

---

### Task 8: `StreamTopicsList` component

**Files:**
- Create: `frontend/src/components/StreamTopicsList.tsx`

Shows stream topics in a card list. Each card has: title, is_news badge, summary, last_seen_at. Mirrors the visual style of `ItemsTable` (padding 24, bg var(--white) cards, muted metadata).

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/components/StreamTopicsList.tsx
import type { StreamTopic } from "../types";
import { StatusMessage } from "./ui/StatusMessage";
import { useT } from "../i18n";

interface Props {
  topics: StreamTopic[];
  loading: boolean;
}

function relTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

export function StreamTopicsList({ topics, loading }: Props) {
  const t = useT();

  if (loading) return <StatusMessage kind="loading">{t.streams.topic.loading}</StatusMessage>;
  if (topics.length === 0)
    return <StatusMessage kind="empty">{t.streams.topic.noTopics}</StatusMessage>;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12 }}>
      {topics.map((topic) => (
        <div
          key={topic.topic_id}
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 16,
            background: "var(--white)",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 6 }}>
            <span
              style={{
                fontSize: 11,
                padding: "2px 7px",
                borderRadius: 999,
                flexShrink: 0,
                background: topic.is_news ? "var(--accent-lt)" : "var(--bg)",
                color: topic.is_news ? "var(--accent)" : "var(--muted)",
                border: `1px solid ${topic.is_news ? "var(--accent)" : "var(--border)"}`,
              }}
            >
              {topic.is_news ? t.streams.topic.newsBadge : t.streams.topic.notNewsBadge}
            </span>
            <span style={{ fontWeight: 600, color: "var(--text)", flex: 1 }}>{topic.title}</span>
            <span style={{ fontSize: 11, color: "var(--muted)", flexShrink: 0 }}>
              {t.streams.topic.lastSeen}: {relTime(topic.last_seen_at)}
            </span>
          </div>
          {topic.summary && (
            <p style={{ margin: 0, fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
              {topic.summary}
            </p>
          )}
          {topic.speakers.length > 0 && (
            <p style={{ margin: "6px 0 0", fontSize: 11, color: "var(--muted)" }}>
              {topic.speakers.map((s) => s.name_or_role).join(", ")}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Type-check + test**

```
cd frontend && npx tsc --noEmit && npm test
```

Expected: 0 errors, tests pass.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/StreamTopicsList.tsx
git commit -m "feat(streams): StreamTopicsList component"
```

---

### Task 9: `StreamsConfigSection` component

**Files:**
- Create: `frontend/src/components/StreamsConfigSection.tsx`

Settings form for adding and deleting stream subscriptions. Uses `useStreamSubscriptions` directly. Renders as a standalone form — no DomainConfig dependency. The "add stream" form has fields: name, stream_url, stream_type (default "radio"), url_refresh_url (optional), url_refresh_field (default "url"), chunk_duration_seconds (default 180).

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/components/StreamsConfigSection.tsx
import { useState } from "react";
import { useStreamSubscriptions } from "../lib/useStreamSubscriptions";
import { useT } from "../i18n";

const EMPTY_FORM = {
  name: "",
  stream_url: "",
  stream_type: "radio",
  url_refresh_url: "",
  url_refresh_field: "url",
  chunk_duration_seconds: 180,
};

export function StreamsConfigSection() {
  const t = useT();
  const { subscriptions, loading, create, remove } = useStreamSubscriptions();
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "6px 8px",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    fontSize: 13,
    color: "var(--text)",
    background: "var(--white)",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    color: "var(--muted)",
    display: "block",
    marginBottom: 3,
  };

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.stream_url.trim()) return;
    setSaving(true);
    try {
      await create({
        name: form.name.trim(),
        stream_url: form.stream_url.trim(),
        stream_type: form.stream_type.trim() || "radio",
        url_refresh_url: form.url_refresh_url.trim() || undefined,
        url_refresh_field: form.url_refresh_field.trim() || "url",
        chunk_duration_seconds: form.chunk_duration_seconds,
      });
      setForm(EMPTY_FORM);
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2000);
    } catch (err) {
      console.error("StreamsConfigSection: create failed", err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 640 }}>
      <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
        {t.streams.config.sectionStreams}
      </h2>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 24 }}>
        {t.streams.config.streamsHint}
      </p>

      {/* Existing subscriptions */}
      {!loading && subscriptions.length > 0 && (
        <div style={{ marginBottom: 24, display: "flex", flexDirection: "column", gap: 8 }}>
          {subscriptions.map((sub) => (
            <div
              key={sub.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "8px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                background: "var(--white)",
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontWeight: 500, fontSize: 13 }}>{sub.name}</span>
                <span
                  style={{
                    marginLeft: 8,
                    fontSize: 11,
                    color: "var(--muted)",
                    textTransform: "uppercase",
                  }}
                >
                  {sub.stream_type}
                </span>
                <div
                  style={{
                    fontSize: 11,
                    color: "var(--muted)",
                    fontFamily: "ui-monospace, Menlo, monospace",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {sub.stream_url}
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (window.confirm(t.streams.subscription.confirmDelete)) {
                    void remove(sub.id);
                  }
                }}
                style={{
                  fontSize: 12,
                  color: "var(--error-fg)",
                  background: "none",
                  border: "1px solid var(--error-fg)",
                  borderRadius: "var(--radius)",
                  padding: "3px 10px",
                  cursor: "pointer",
                  flexShrink: 0,
                }}
              >
                {t.streams.config.removeStream}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add stream form */}
      <form onSubmit={(e) => void handleAdd(e)}>
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 16,
            background: "var(--bg)",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>{t.streams.config.streamName}</label>
              <input
                style={inputStyle}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder={t.streams.config.streamNamePlaceholder}
              />
            </div>
            <div>
              <label style={labelStyle}>{t.streams.config.streamType}</label>
              <input
                style={inputStyle}
                value={form.stream_type}
                onChange={(e) => setForm((f) => ({ ...f, stream_type: e.target.value }))}
                placeholder={t.streams.config.streamTypePlaceholder}
              />
            </div>
          </div>
          <div>
            <label style={labelStyle}>{t.streams.config.streamUrl}</label>
            <input
              style={inputStyle}
              value={form.stream_url}
              onChange={(e) => setForm((f) => ({ ...f, stream_url: e.target.value }))}
              placeholder={t.streams.config.streamUrlPlaceholder}
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12 }}>
            <div>
              <label style={labelStyle}>{t.streams.config.urlRefreshUrl}</label>
              <input
                style={inputStyle}
                value={form.url_refresh_url}
                onChange={(e) => setForm((f) => ({ ...f, url_refresh_url: e.target.value }))}
                placeholder={t.streams.config.urlRefreshUrlPlaceholder}
              />
            </div>
            <div>
              <label style={labelStyle}>{t.streams.config.urlRefreshField}</label>
              <input
                style={{ ...inputStyle, width: 100 }}
                value={form.url_refresh_field}
                onChange={(e) => setForm((f) => ({ ...f, url_refresh_field: e.target.value }))}
                placeholder="url"
              />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
            <div>
              <label style={labelStyle}>{t.streams.config.chunkDuration}</label>
              <input
                type="number"
                style={{ ...inputStyle, width: 100 }}
                value={form.chunk_duration_seconds}
                min={30}
                max={600}
                onChange={(e) =>
                  setForm((f) => ({ ...f, chunk_duration_seconds: Number(e.target.value) }))
                }
              />
            </div>
            <button
              type="submit"
              disabled={saving || !form.name.trim() || !form.stream_url.trim()}
              style={{
                padding: "7px 18px",
                background: "var(--accent)",
                color: "var(--white)",
                border: "none",
                borderRadius: "var(--radius)",
                fontSize: 13,
                fontWeight: 500,
                cursor: saving ? "default" : "pointer",
                opacity: saving || !form.name.trim() || !form.stream_url.trim() ? 0.6 : 1,
              }}
            >
              {saving ? t.streams.config.saving : t.streams.config.addStream}
            </button>
            {savedMsg && (
              <span style={{ fontSize: 12, color: "var(--success-fg)" }}>
                {t.streams.config.saved}
              </span>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Type-check + test**

```
cd frontend && npx tsc --noEmit && npm test
```

Expected: 0 errors, tests pass.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/StreamsConfigSection.tsx
git commit -m "feat(streams): StreamsConfigSection settings form"
```

---

### Task 10: Wire into `DiscoveryHub`

**Files:**
- Modify: `frontend/src/components/DiscoveryHub.tsx`

Add 2 tabs to the existing 3. The existing `DiscoveryView` union type gets 2 new members. Stream hooks are called unconditionally (like `useDiscoveryFeeds`) — they return empty arrays before auth is ready. The filter sidebar stays visible for all tabs (no filter for streams yet, but sidebar already collapses gracefully when feeds/categories are empty).

- [ ] **Step 1: Extend imports and view type**

At the top of `frontend/src/components/DiscoveryHub.tsx`, add to the existing imports:

```typescript
import { useStreamSubscriptions } from "../lib/useStreamSubscriptions";
import { useStreamTopics } from "../lib/useStreamTopics";
import { StreamsHealth } from "./StreamsHealth";
import { StreamTopicsList } from "./StreamTopicsList";
import { StreamsIcon, StreamTopicsIcon } from "./ui/icons";
```

Change line 18:
```typescript
// before:
type DiscoveryView = "topics" | "items" | "feeds";
// after:
type DiscoveryView = "topics" | "items" | "feeds" | "streamy" | "tematy-streamow";
```

- [ ] **Step 2: Add hook calls**

Inside `DiscoveryHub()`, after the existing hook calls (after line 44 `const { items, loading: itemsLoading } = useDiscoveryItems(...)`), add:

```typescript
  const { subscriptions, loading: subsLoading, remove: removeSub } = useStreamSubscriptions();
  const { topics: streamTopics, loading: streamTopicsLoading } = useStreamTopics();
```

- [ ] **Step 3: Add tab buttons**

In the tab bar (after the `<FeedsIcon /> {t.discovery.views.feeds}` button, before the sort dropdown `div`), add:

```typescript
          <button
            type="button"
            onClick={() => setView("streamy")}
            disabled={view === "streamy"}
            style={{ ...tabBtn(view === "streamy"), display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <StreamsIcon /> {t.streams.views.subscriptions}
          </button>
          <button
            type="button"
            onClick={() => setView("tematy-streamow")}
            disabled={view === "tematy-streamow"}
            style={{ ...tabBtn(view === "tematy-streamow"), display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <StreamTopicsIcon /> {t.streams.views.topics}
          </button>
```

- [ ] **Step 4: Add view rendering**

In the content area (after `{view === "feeds" && <FeedsHealth feeds={feeds} loading={feedsLoading} />}`), add:

```typescript
              {view === "streamy" && (
                <StreamsHealth
                  subscriptions={subscriptions}
                  loading={subsLoading}
                  onDelete={removeSub}
                />
              )}
              {view === "tematy-streamow" && (
                <StreamTopicsList topics={streamTopics} loading={streamTopicsLoading} />
              )}
```

- [ ] **Step 5: Type-check + test**

```
cd frontend && npx tsc --noEmit && npm test
```

Expected: 0 errors, tests pass.

- [ ] **Step 6: Commit**

```
git add frontend/src/components/DiscoveryHub.tsx
git commit -m "feat(streams): Streamy + Tematy streamów tabs in DiscoveryHub"
```

---

### Task 11: Wire into Settings

**Files:**
- Modify: `frontend/src/components/SettingsNav.tsx`
- Modify: `frontend/src/components/SettingsView.tsx`

`SettingsView` branches on `activeSection === "streamy"` to render `StreamsConfigSection` instead of `DomainConfigForm`. This keeps `DomainConfigForm` completely untouched.

- [ ] **Step 1: Add "streamy" to `SettingsNav`**

In `frontend/src/components/SettingsNav.tsx`:

Change line 3:
```typescript
// before:
const SECTION_IDS = ["podstawowe", "modele", "wyszukiwanie", "media", "wytyczne", "html", "stance", "tytuly", "przyklady", "szablony", "discovery"] as const;
// after:
const SECTION_IDS = ["podstawowe", "modele", "wyszukiwanie", "media", "wytyczne", "html", "stance", "tytuly", "przyklady", "szablony", "discovery", "streamy"] as const;
```

Add to the `labels` object (after `discovery: t.settingsNav.discovery,`):
```typescript
    streamy: t.settingsNav.streams,
```

- [ ] **Step 2: Branch in `SettingsView`**

In `frontend/src/components/SettingsView.tsx`:

Add import at the top:
```typescript
import { StreamsConfigSection } from "./StreamsConfigSection";
```

Replace the `<DomainConfigForm .../>` with:
```typescript
      {activeSection === "streamy" ? (
        <StreamsConfigSection />
      ) : (
        <DomainConfigForm
          initialConfig={config}
          activeSection={activeSection}
          saving={saving}
          error={error}
          onSave={save}
        />
      )}
```

- [ ] **Step 3: Type-check + full test suite**

```
cd frontend && npx tsc --noEmit && npm test
```

Then backend:
```
uv run pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```
git add frontend/src/components/SettingsNav.tsx frontend/src/components/SettingsView.tsx
git commit -m "feat(streams): wire streams into Settings nav and SettingsView"
```

---

## Self-Review

**Spec coverage:**
- ✅ Stream settings configuration — Task 9 + 11
- ✅ Discovery tab "Streamy" with subscription stats (live/not live) — Task 7 + 10
- ✅ Discovery tab "Tematy streamów" with discovered topics — Task 8 + 10
- ✅ Consistent with existing patterns (FeedsHealth, useDiscoveryFeeds, SettingsNav) — all tasks follow existing file structure and styling
- ✅ Modular/isolated — new files prefixed Streams*, DomainConfigForm untouched, easy to remove entire feature by reverting 2 modifications and deleting 5 files

**Placeholder scan:** None found. All code blocks are complete.

**Type consistency:**
- `StreamSubscription` defined in Task 2, used in Tasks 5, 7, 9
- `StreamTopic` defined in Task 2, used in Tasks 6, 8
- `t.streams.*` keys defined in Task 3, used in Tasks 7, 8, 9
- `StreamsIcon`, `StreamTopicsIcon` defined in Task 4, used in Task 10
- `useStreamSubscriptions` defined in Task 5, used in Tasks 9, 10
- `useStreamTopics` defined in Task 6, used in Task 10
- `removeSub` in Task 10 comes from `remove` returned by `useStreamSubscriptions` — matches `remove: (id: string) => Promise<void>` defined in Task 5
