# App UI Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the authenticated app's design language with the landing page — card components, pill navigation, icon containers, landing-style typography, custom filter sidebar, and sidebar two-line article layout.

**Architecture:** Pure CSS/inline-style changes in React. No new dependencies. All changes are in `frontend/src/`. Each task is one commit. After each phase the dev server is checked visually before proceeding.

**Tech Stack:** React 18, TypeScript, Vite, inline styles + CSS custom properties (tokens.css). Verify with `npx tsc --noEmit` (from `frontend/`) after every task.

---

## Files Modified

| File | What changes |
|------|-------------|
| `frontend/src/components/TopicDetail.tsx` | Token fix + card wrappers |
| `frontend/src/components/NewArticleForm.tsx` | Token fix + modal overlay |
| `frontend/src/components/DiscoveryHub.tsx` | Tab pills + sort select |
| `frontend/src/components/DiscoveryFiltersSidebar.tsx` | details→custom styled |
| `frontend/src/components/TopicCard.tsx` | Cards + chips + icons + source cards |
| `frontend/src/components/ui/icons.tsx` | Add RadioIcon, ExternalLinkIcon, PlayIcon |
| `frontend/src/components/ArticleView.tsx` | Running state framing |
| `frontend/src/components/Sidebar.tsx` | Two-line article layout |
| `frontend/src/components/CollapsibleSection.tsx` | Padding + icon box |
| `frontend/src/components/ui/Button.tsx` | radius + weight + hover |
| `frontend/src/styles/tokens.css` | Chrome scrollbar class |
| `frontend/src/components/DateRangePicker.tsx` | Token fix + modal shadow + radius |

---

## Phase 1 — Token cleanup

### Task 1: TopicDetail.tsx — legacy token fix + meta card

**Files:**
- Modify: `frontend/src/components/TopicDetail.tsx`

- [ ] **Step 1: Replace all legacy tokens**

Open `frontend/src/components/TopicDetail.tsx`. Use find-and-replace (replace_all):

```
"var(--white)"  →  "var(--card-bg)"
"var(--border)"  →  "var(--card-border)"   (only those not already var(--card-border))
"var(--muted)"  →  "var(--ink-subtle)"
"var(--text)"   →  "var(--ink)"
```

Confirm: `grep -n "var(--white)\|var(--border)\|var(--muted)\"" frontend/src/components/TopicDetail.tsx` should return 0 lines after.

- [ ] **Step 2: Wrap right aside meta in a card**

Find the `<aside>` element (line ~322). Replace the plain `<div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.8 }}>` wrapping the meta rows with a card:

```tsx
<aside>
  {isConsumed ? (
    <button
      type="button"
      disabled
      style={{
        width: "100%",
        padding: "10px 16px",
        background: "var(--canvas-bg)",
        color: "var(--ink-subtle)",
        border: "1px solid var(--card-border)",
        borderRadius: "var(--radius)",
        cursor: "default",
        fontWeight: 500,
        marginBottom: 12,
        fontSize: 14,
        fontFamily: "inherit",
      }}
    >
      {t.discovery.topic.openArticle}
    </button>
  ) : (
    <Button
      variant="primary"
      size="md"
      style={{ width: "100%", marginBottom: 12 }}
      onClick={() => onWrite(topicId)}
    >
      {t.discovery.topic.writeArticle}
    </Button>
  )}
  <div style={{
    background: "var(--card-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: 10,
    padding: "14px 16px",
    boxShadow: "var(--shadow-card)",
  }}>
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {[
        { label: t.discovery.topic.firstSeen, value: detail.first_seen_at ? new Date(detail.first_seen_at).toLocaleString() : "—" },
        { label: t.discovery.topic.lastActivity, value: new Date(detail.last_activity_at).toLocaleString() },
        { label: t.discovery.topic.statusLabel, value: detail.status },
        { label: t.discovery.topic.itemsCount, value: String(detail.items.length) },
      ].map(({ label, value }) => (
        <div key={label}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".1em", textTransform: "uppercase", color: "var(--ink-subtle)", marginBottom: 2 }}>{label}</div>
          <div style={{ fontSize: 13, color: "var(--ink)", fontWeight: 500 }}>{value}</div>
        </div>
      ))}
    </div>
  </div>
</aside>
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TopicDetail.tsx
git commit -m "fix(ui): TopicDetail — legacy token fix + meta panel card"
```

---

### Task 2: NewArticleForm.tsx — legacy token fix

**Files:**
- Modify: `frontend/src/components/NewArticleForm.tsx`

- [ ] **Step 1: Replace all legacy tokens**

Open `frontend/src/components/NewArticleForm.tsx`. Use replace_all:

```
"var(--white)"  →  "var(--card-bg)"
"var(--border)"  →  "var(--card-border)"
```

Note: `var(--muted)` and `var(--text)` may also appear — replace:
```
"var(--muted)"  →  "var(--ink-subtle)"
"var(--text)"   →  "var(--ink)"
```

Verify: `grep -n "var(--white)\|\"var(--border)\"" frontend/src/components/NewArticleForm.tsx` → 0 results.

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/NewArticleForm.tsx
git commit -m "fix(ui): NewArticleForm — 27 legacy token occurrences replaced"
```

---

## Phase 2 — Discovery redesign

### Task 3: DiscoveryHub.tsx — tab pills + sort select

**Files:**
- Modify: `frontend/src/components/DiscoveryHub.tsx`

- [ ] **Step 1: Replace tabBtn with pill style**

Find the `tabBtn` function (around line 125) and replace entirely:

```tsx
const tabBtn = (active: boolean): React.CSSProperties => ({
  padding: "5px 14px",
  background: active ? "var(--accent)" : "transparent",
  border: "none",
  borderRadius: 999,
  color: active ? "#fff" : "var(--ink-subtle)",
  cursor: active ? "default" : "pointer",
  fontSize: 13,
  fontWeight: active ? 600 : 500,
  transition: "background .15s, color .15s",
  fontFamily: "inherit",
});
```

- [ ] **Step 2: Add icon container wrapper to each tab button**

Each tab button currently renders like: `style={{ ...tabBtn(view === "topics"), display: "inline-flex", alignItems: "center", gap: 6 }}` with an icon directly inside.

Add an `iconBox` helper right above the return:

```tsx
const iconBox = (active: boolean): React.CSSProperties => ({
  width: 18,
  height: 18,
  borderRadius: 5,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  background: active ? "rgba(255,255,255,.2)" : "var(--accent-lt)",
  flexShrink: 0,
});
```

Update every tab button to wrap its icon. Example for the "topics" tab:

```tsx
<button
  type="button"
  onClick={() => setView("topics")}
  disabled={view === "topics"}
  style={{ ...tabBtn(view === "topics"), display: "inline-flex", alignItems: "center", gap: 7 }}
>
  <span style={iconBox(view === "topics")}><TopicsIcon /></span>
  {t.discovery.views.topics}
</button>
```

Apply the same pattern to all 5 tab buttons (topics, items, tematy-streamow, feeds, streamy).

- [ ] **Step 3: Update tab bar container style**

Find the outer div that holds the tab buttons (currently `padding: "12px 24px"`, `background: "var(--card-bg)"`). Update:

```tsx
style={{
  borderBottom: "1px solid var(--card-border)",
  padding: "10px 20px",
  display: "flex",
  gap: 4,
  alignItems: "center",
  background: "var(--card-bg)",
}}
```

- [ ] **Step 4: Update sort select style**

Find the `<select>` in the sort bar and replace its style:

```tsx
style={{
  padding: "5px 28px 5px 10px",
  border: "1px solid var(--card-border)",
  borderRadius: "var(--radius)",
  background: "var(--card-bg)",
  color: "var(--ink)",
  fontSize: 13,
  cursor: "pointer",
  fontFamily: "inherit",
  appearance: "none" as React.CSSProperties["appearance"],
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2' stroke-linecap='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 8px center",
  boxShadow: "var(--shadow-card)",
}}
```

Also fix sort bar label and container tokens:

```tsx
// Sort bar container (padding: "6px 24px"):
style={{
  borderBottom: "1px solid var(--card-border)",
  padding: "6px 20px",
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  gap: 8,
  background: "var(--card-bg)",
}}

// Sort bar label:
style={{ fontSize: 12, color: "var(--ink-subtle)" }}
```

Also fix the scroll area background:
```tsx
// The div with flex: 1, overflow: "auto":
style={{ flex: 1, overflow: "auto", background: "var(--canvas-bg)" }}
```

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/DiscoveryHub.tsx
git commit -m "feat(ui): Discovery tab bar — pill navigation + icon containers + sort select"
```

---

### Task 4: DiscoveryFiltersSidebar.tsx — custom styled sections

**Files:**
- Modify: `frontend/src/components/DiscoveryFiltersSidebar.tsx`

- [ ] **Step 1: Add open/close state for each section**

At the top of the `DiscoveryFiltersSidebar` function, add state:

```tsx
const [feedsOpen, setFeedsOpen] = useState(true);
const [subsOpen, setSubsOpen] = useState(true);
const [catsOpen, setCatsOpen] = useState(true);
const [statusOpen, setStatusOpen] = useState(true);
```

Add `useState` to the import: `import { useState } from "react";`

- [ ] **Step 2: Define shared styles**

Replace the existing `labelStyle`, `buttonRow`, `buttonRowActive` constants with:

```tsx
const sectionLabel: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: ".12em",
  textTransform: "uppercase" as const,
  color: "var(--accent)",
  display: "flex",
  alignItems: "center",
  gap: 7,
  padding: "4px 0 8px",
  marginBottom: 4,
  borderBottom: "1px solid var(--chrome-border)",
  cursor: "pointer",
  userSelect: "none" as const,
  background: "none",
  border: "none",
  width: "100%",
  textAlign: "left" as const,
  fontFamily: "inherit",
};

const dot: React.CSSProperties = {
  width: 5, height: 5, borderRadius: "50%",
  background: "var(--accent)", flexShrink: 0,
};

const chevron = (open: boolean): React.CSSProperties => ({
  marginLeft: "auto",
  color: "var(--chrome-faint)",
  fontSize: 10,
  transition: "transform .15s",
  transform: open ? "rotate(180deg)" : "rotate(0deg)",
  display: "inline-block",
});

const filterBtn: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  width: "100%",
  padding: "5px 8px",
  background: "transparent",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
  color: "var(--chrome-muted)",
  fontSize: 13,
  textAlign: "left" as const,
  transition: "background .12s, color .12s",
  fontFamily: "inherit",
  margin: "1px 0",
};

const filterBtnActive: React.CSSProperties = {
  ...filterBtn,
  background: "rgba(234,88,12,.12)",
  color: "var(--accent-light)",
  fontWeight: 600,
};
```

- [ ] **Step 3: Replace `<details>` blocks with custom collapsible**

Replace all 4 `<details>` sections. Pattern for each:

```tsx
{/* FEEDS section */}
{showFeeds && (
  <div style={{ marginBottom: 14 }}>
    <button type="button" onClick={() => setFeedsOpen(v => !v)} style={sectionLabel}>
      <span style={dot} />
      <span style={{ flex: 1 }}>{t.discovery.filters.feeds}</span>
      <span style={chevron(feedsOpen)}>▾</span>
    </button>
    {feedsOpen && (
      <div>
        <button type="button" onClick={() => setFeed(null)} style={value.feedId === null ? filterBtnActive : filterBtn}>
          <span>{t.discovery.filters.all}</span>
        </button>
        {feeds.map((f) => (
          <button
            type="button"
            key={f.id}
            onClick={() => setFeed(f.id)}
            style={value.feedId === f.id ? filterBtnActive : filterBtn}
          >
            <span>{hostname(f.feed_url)}</span>
            <span style={{ color: "var(--chrome-faint)", fontSize: 11 }}>{f.items_24h_count}</span>
          </button>
        ))}
      </div>
    )}
  </div>
)}

{/* SUBSCRIPTIONS section */}
{showSubscriptions && (
  <div style={{ marginBottom: 14 }}>
    <button type="button" onClick={() => setSubsOpen(v => !v)} style={sectionLabel}>
      <span style={dot} />
      <span style={{ flex: 1 }}>{t.discovery.filters.streams}</span>
      <span style={chevron(subsOpen)}>▾</span>
    </button>
    {subsOpen && (
      <div>
        <button type="button" onClick={() => setSubscription(null)} style={value.subscriptionId === null ? filterBtnActive : filterBtn}>
          <span>{t.discovery.filters.all}</span>
        </button>
        {subscriptions.map((s) => (
          <button
            type="button"
            key={s.id}
            onClick={() => setSubscription(s.id)}
            style={value.subscriptionId === s.id ? filterBtnActive : filterBtn}
          >
            <span>{s.name}</span>
            <span style={{
              width: 8, height: 8, borderRadius: "50%",
              background: s.status === "active" ? "var(--success)" : "var(--chrome-faint)",
              flexShrink: 0,
            }} />
          </button>
        ))}
      </div>
    )}
  </div>
)}

{/* CATEGORIES section */}
<div style={{ marginBottom: 14 }}>
  <button type="button" onClick={() => setCatsOpen(v => !v)} style={sectionLabel}>
    <span style={dot} />
    <span style={{ flex: 1 }}>{t.discovery.filters.categories}</span>
    <span style={chevron(catsOpen)}>▾</span>
  </button>
  {catsOpen && (
    <div>
      {availableCategories.length === 0 && (
        <div style={{ color: "var(--chrome-faint)", fontSize: 12, padding: "4px 8px" }}>
          {t.discovery.filters.emptyCategories}
        </div>
      )}
      {availableCategories.map((c) => (
        <label key={c.name} style={{ display: "flex", justifyContent: "space-between", gap: 8, padding: "4px 8px", fontSize: 13, cursor: "pointer", color: "var(--chrome-muted)" }}>
          <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={value.categories.includes(c.name)} onChange={() => toggleCategory(c.name)} style={{ accentColor: "var(--accent)" }} />
            {c.name}
          </span>
          {c.count !== undefined && <span style={{ color: "var(--chrome-faint)", fontSize: 11 }}>{c.count}</span>}
        </label>
      ))}
    </div>
  )}
</div>

{/* STATUS section */}
{showStatuses && (
  <div>
    <button type="button" onClick={() => setStatusOpen(v => !v)} style={sectionLabel}>
      <span style={dot} />
      <span style={{ flex: 1 }}>{t.discovery.filters.status}</span>
      <span style={chevron(statusOpen)}>▾</span>
    </button>
    {statusOpen && (
      <div>
        {[
          { id: "open", label: t.discovery.status.open },
          { id: "resurfaced", label: t.discovery.status.resurfaced },
          { id: "consumed", label: t.discovery.status.consumed },
          { id: "dismissed", label: t.discovery.status.dismissed },
        ].map((s) => (
          <label key={s.id} style={{ display: "flex", gap: 8, padding: "4px 8px", fontSize: 13, cursor: "pointer", color: "var(--chrome-muted)" }}>
            <input type="checkbox" checked={value.statuses.includes(s.id)} onChange={() => toggleStatus(s.id)} style={{ accentColor: "var(--accent)" }} />
            {s.label}
          </label>
        ))}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 4: Remove old `labelStyle`, `buttonRow`, `buttonRowActive` constants** (now replaced above)

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/DiscoveryFiltersSidebar.tsx
git commit -m "feat(ui): DiscoveryFiltersSidebar — replace details/summary with custom styled collapsible"
```

---

### Task 5: TopicCard.tsx — cards + crisp chips + section label

**Files:**
- Modify: `frontend/src/components/TopicCard.tsx`

- [ ] **Step 1: Replace legacy tokens**

```
"var(--white)"  →  "var(--card-bg)"
"var(--border)"  →  "var(--card-border)"
"var(--muted)"  →  "var(--ink-subtle)"
"var(--text)"   →  "var(--ink)"
```

- [ ] **Step 2: Convert outer wrapper to card with shadow + hover**

Find the outermost div (line ~137):
```tsx
// Replace:
<div
  style={{
    padding: "16px 24px",
    borderBottom: "1px solid var(--border)",
    background: "var(--white)",
  }}
>

// With:
<div
  style={{
    margin: "0 12px 8px",
    background: "var(--card-bg)",
    border: "1px solid var(--card-border)",
    borderRadius: 12,
    boxShadow: "var(--shadow-card)",
    padding: "16px 20px",
    transition: "box-shadow .2s, border-color .2s",
  }}
  onMouseEnter={(e) => {
    e.currentTarget.style.boxShadow = "var(--shadow-card-hover)";
    e.currentTarget.style.borderColor = "var(--card-border-strong)";
  }}
  onMouseLeave={(e) => {
    e.currentTarget.style.boxShadow = "var(--shadow-card)";
    e.currentTarget.style.borderColor = "var(--card-border)";
  }}
>
```

- [ ] **Step 3: Add fontWeight:600 and solid borders to chipBase**

Find `chipBase` constant (line ~127):
```tsx
const chipBase: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "2px 8px",
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 600,
};
```

Update all chip usages to add solid border:
```tsx
// Accent chip:
{ ...chipBase, background: "var(--accent-tint)", color: "var(--accent)", border: "1px solid var(--accent-border)" }

// Success chip (written):
{ ...chipBase, background: "var(--success-tint)", color: "var(--success-fg)", border: "1px solid #bbf7d0" }

// Error chip (resurfaced):
{ ...chipBase, background: "var(--error-tint)", color: "var(--error-fg)", border: "1px solid #fecaca" }
```

- [ ] **Step 4: Update expanded sources section**

Find the expanded sources section (line ~326). Change the wrapper from left-border style to a card:

```tsx
{open && (
  <div
    style={{
      marginTop: 12,
      padding: "12px 14px",
      background: "var(--canvas-bg)",
      borderRadius: 8,
      border: "1px solid var(--card-border)",
    }}
  >
```

Update the section label at the top of expanded sources:
```tsx
// Replace:
<div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--muted)", marginBottom: 6, letterSpacing: "0.04em" }}>

// With:
<div style={{
  fontSize: 10, fontWeight: 700, letterSpacing: ".12em", textTransform: "uppercase",
  color: "var(--accent)", marginBottom: 10,
  display: "flex", alignItems: "center", gap: 6,
}}>
  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)", flexShrink: 0 }} />
```
(Close the div after `{t.discovery.topic.sources}`)

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/TopicCard.tsx
git commit -m "feat(ui): TopicCard — card style with shadow, crisp chips, source section label"
```

---

## Phase 3 — Icons & badges

### Task 6: Add new icons + replace emoji

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx`
- Modify: `frontend/src/components/TopicCard.tsx`

- [ ] **Step 1: Add RadioIcon, ExternalLinkIcon, PlayIcon to ui/icons.tsx**

Append at the end of `frontend/src/components/ui/icons.tsx`:

```tsx
export function RadioIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <circle cx="12" cy="20" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ExternalLinkIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

export function PlayIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}
```

- [ ] **Step 2: Add MetaIconBox helper and wrap meta icons in TopicCard.tsx**

At the top of `TopicCard.tsx`, add import:
```tsx
import { RadioIcon } from "./ui/icons";
```

Add a helper function inside the file (before the component):
```tsx
function MetaIconBox({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      width: 24, height: 24, borderRadius: 6,
      background: "var(--accent-tint)", color: "var(--accent)",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      flexShrink: 0,
    }}>
      {children}
    </span>
  );
}
```

Update each `<span style={metaItem}>` that contains an icon to use the box:
```tsx
// Sources:
<span style={metaItem}>
  <MetaIconBox><SourcesIcon /></MetaIconBox>
  {topic.item_count + topic.stream_source_count} {t.discovery.hub.sourcesCount}
  {topic.stream_source_count > 0 && (
    <span style={{ color: "var(--accent)", fontWeight: 500, marginLeft: 4, display: "inline-flex", alignItems: "center", gap: 3 }}>
      · <RadioIcon width={10} height={10} /> {topic.stream_source_count}
    </span>
  )}
</span>

// Calendar:
<span style={metaItem} title={t.discovery.topic.firstSeen}>
  <MetaIconBox><CalendarIcon /></MetaIconBox>
  {t.discovery.topic.firstSeenShort}: {new Date(topic.first_seen_at).toLocaleString()}
</span>

// Clock:
<span style={metaItem} title={t.discovery.topic.lastActivity}>
  <MetaIconBox><ClockIcon /></MetaIconBox>
  {t.discovery.topic.lastActivityShort}: {new Date(topic.last_activity_at).toLocaleString()}
</span>

// Globe:
<span style={metaItem}>
  <MetaIconBox><GlobeIcon /></MetaIconBox>
  {topic.feed_hosts.join(", ")}
</span>
```

- [ ] **Step 3: Replace 📡 emoji in stream source badge (TopicCard.tsx)**

Find the stream source badge inside the expanded sources map (the `📡 {src.subscription_name}` span):

```tsx
// Replace:
<span style={{ fontSize: 10, fontWeight: 600, color: "var(--accent)", background: "var(--accent-lt)", borderRadius: 4, padding: "1px 6px", flexShrink: 0 }}>
  📡 {src.subscription_name}
</span>

// With:
<span style={{
  fontSize: 10, fontWeight: 600, color: "var(--accent)",
  background: "var(--accent-tint)", border: "1px solid var(--accent-border)",
  borderRadius: 4, padding: "1px 6px", flexShrink: 0,
  display: "inline-flex", alignItems: "center", gap: 4,
}}>
  <RadioIcon width={10} height={10} />
  {src.subscription_name}
</span>
```

- [ ] **Step 4: Replace emoji in SocialMediaAttachmentCard (ArticleView.tsx)**

Open `frontend/src/components/ArticleView.tsx`. Add to import: `PlayIcon` from the icons import line.

Find `SocialMediaAttachmentCard`:

```tsx
// Remove this line:
const platformIcon = isInstagram ? "📸" : "𝕏";

// Remove the span:
<span style={{ fontSize: 16, lineHeight: 1 }}>{platformIcon}</span>

// The platformLabel line below it already shows "Instagram"/"X.com" text — that's sufficient.
// The platform badge already has: <span style={{ fontSize: 11, fontWeight: 700 ...}}>{platformLabel}</span>
```

Replace download button content:
```tsx
// Find: {downloading ? "⏳" : "⬇"} {isVideo...}
// Replace:
{downloading ? (
  <span style={{ display: "inline-block", width: 13, height: 13, border: "2px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
) : (
  <DownloadIcon width={13} height={13} />
)}{" "}{isVideo ? t.socialMediaDownloadVideo : t.socialMediaDownloadPhoto}
```

Replace play link content:
```tsx
// Find: ▶ {t.socialMediaOpenVideo}
// Replace:
<><PlayIcon width={13} height={13} />{" "}{t.socialMediaOpenVideo}</>
```

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/icons.tsx frontend/src/components/TopicCard.tsx frontend/src/components/ArticleView.tsx
git commit -m "feat(ui): icon containers on TopicCard meta row, RadioIcon, replace emoji with SVG"
```

---

## Phase 4 — Modals, running state, sidebar layout

### Task 7: Modal overlay — backdrop blur + deep shadow

**Files:**
- Modify: `frontend/src/components/NewArticleForm.tsx`

- [ ] **Step 1: Update modal overlay background**

In `NewArticleForm.tsx`, find the outermost fixed overlay div (the one with `position: "fixed"`, `inset: 0` or equivalent covering the whole screen). Update its background and add backdrop-filter:

```tsx
// Find the overlay div style. It likely has: background: "rgba(0,0,0,.5)" or similar.
// Replace background line with:
background: "rgba(13,17,23,.65)",
backdropFilter: "blur(4px)",
WebkitBackdropFilter: "blur(4px)",
```

- [ ] **Step 2: Update modal box shadow and radius**

Find the inner modal content div (referenced via `dialogRef`). Update or add:

```tsx
boxShadow: "var(--shadow-modal)",  // 0 24px 64px rgba(13,17,23,.25)
borderRadius: 14,
```

Find the modal title / header area. Update `fontWeight` to 800 and add `letterSpacing: "-.025em"`.

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/NewArticleForm.tsx
git commit -m "feat(ui): NewArticleForm modal — backdrop blur + deep shadow"
```

---

### Task 8: ArticleView.tsx — running state framing

**Files:**
- Modify: `frontend/src/components/ArticleView.tsx`

- [ ] **Step 1: Wrap running spinner + label in a framed container**

Find the running state return (around line 107). The current spinner+label div:

```tsx
// Replace:
<div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)", fontSize: 14 }}>
  <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
  {stageLabel}
</div>

// With:
<div style={{
  display: "inline-flex",
  alignItems: "center",
  gap: 10,
  padding: "12px 16px",
  background: "var(--warning-lt)",
  border: "1px solid rgba(217,119,6,.3)",
  borderRadius: "var(--radius)",
  color: "var(--warning-fg)",
  fontSize: 13,
  marginTop: 4,
}}>
  <span style={{
    display: "inline-block", width: 14, height: 14,
    border: "2px solid var(--warning)", borderTopColor: "transparent",
    borderRadius: "50%", animation: "spin 0.8s linear infinite", flexShrink: 0,
  }} />
  {stageLabel}
</div>
```

- [ ] **Step 2: Also update h2 title in the running state to match article view typography**

Find the `<h2>` in the running state (line ~115):
```tsx
// Replace:
<h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>{article.topic}</h2>

// With:
<h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-.025em", marginBottom: 12 }}>{article.topic}</h2>
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ArticleView.tsx
git commit -m "feat(ui): ArticleView running state — framed warning container, tighter h2 typography"
```

---

### Task 9: Sidebar.tsx — two-line article layout

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Rewrite the article item button structure**

Find the `.map((a) => {` that renders each article (line ~271). The entire button JSX (from `<button key={a.id}` to its closing `</button>`) needs to change.

Replace the entire button body:

```tsx
<button
  key={a.id}
  onClick={() => onSelect(a.id)}
  style={{
    display: "flex",
    alignItems: "flex-start",
    width: "100%",
    padding: "11px 14px",
    background: isSelected
      ? a.marked_done
        ? "rgba(234, 88, 12, 0.06)"
        : "var(--accent-lt)"
      : "transparent",
    borderLeft: isSelected ? "3px solid var(--accent)" : "3px solid transparent",
    borderTop: "none",
    borderRight: "none",
    borderBottom: "1px solid var(--chrome-border)",
    textAlign: "left",
    cursor: "pointer",
    transition: "background 0.12s",
    opacity: a.marked_done
      ? 0.55
      : (a.status === "failed" || a.status === "insufficient_sources")
        ? 0.65
        : 1,
  }}
>
  <div style={{ minWidth: 0, flex: 1 }}>
    <div style={{
      fontSize: 13,
      fontWeight: 600,
      letterSpacing: "-.01em",
      display: "-webkit-box",
      WebkitLineClamp: 2,
      WebkitBoxOrient: "vertical" as const,
      overflow: "hidden",
      lineHeight: 1.4,
      color: "var(--chrome-ink)",
    }}>
      {a.topic}
    </div>
    <div style={{
      fontSize: 11,
      color: "var(--chrome-muted)",
      marginTop: 5,
      display: "flex",
      gap: 6,
      alignItems: "center",
      flexWrap: "wrap",
    }}>
      {a.marked_done ? (
        <span style={{ color: "var(--success)", fontWeight: 700, fontSize: 12, flexShrink: 0, lineHeight: 1 }}>✓</span>
      ) : (a.status === "failed" || a.status === "insufficient_sources") ? (
        <span style={{
          width: 12, height: 12, borderRadius: "50%",
          background: "var(--error)", color: "#fff",
          fontSize: 9, fontWeight: 700, flexShrink: 0,
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          lineHeight: 1,
        }}>✕</span>
      ) : (
        <span style={{
          width: 7, height: 7, borderRadius: "50%",
          background: STATUS_DOT[a.status] ?? "#94a3b8",
          flexShrink: 0,
          animation: a.status === "running" ? "pulse-dot 1.8s ease-out infinite" : undefined,
        }} />
      )}
      <span>{a.created_at ? new Date(a.created_at).toLocaleDateString(lang) : "—"}</span>
      {isMine && (
        <span style={{
          background: "rgba(234,88,12,.12)",
          color: "var(--accent-light)",
          borderRadius: 999,
          padding: "1px 7px",
          fontSize: 10,
          fontWeight: 600,
          lineHeight: "16px",
          border: "1px solid var(--accent-border)",
        }}>
          {t.sidebar.mine}
        </span>
      )}
    </div>
  </div>
</button>
```

Note: The old structure had `gap: 10` and a leading dot/indicator as a sibling of the text div. The new structure has no leading indicator — the indicator moves into the meta row. Remove the old indicator spans from being siblings.

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat(ui): Sidebar article list — two-line title, status dot + date + mine chip in meta row"
```

---

## Phase 5 — Polish

### Task 10: tokens.css — chrome scrollbar + apply to components

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/DiscoveryFiltersSidebar.tsx`

- [ ] **Step 1: Add chrome scrollbar class to tokens.css**

Append at the end of `frontend/src/styles/tokens.css`:

```css
/* Chrome area scrollbar — dark thumb for dark backgrounds */
.chrome-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
.chrome-scroll::-webkit-scrollbar-track { background: transparent; }
.chrome-scroll::-webkit-scrollbar-thumb { background: var(--chrome-border); border-radius: 2px; }
.chrome-scroll::-webkit-scrollbar-thumb:hover { background: var(--chrome-faint); }
```

- [ ] **Step 2: Apply to Sidebar scroll area**

In `Sidebar.tsx`, find the `<div style={{ overflowY: "auto", flex: 1 }}>` and add `className="chrome-scroll"`:

```tsx
<div style={{ overflowY: "auto", flex: 1 }} className="chrome-scroll">
```

- [ ] **Step 3: Apply to DiscoveryFiltersSidebar**

In `DiscoveryFiltersSidebar.tsx`, find the outer `<aside>` and add `className="chrome-scroll"`:

```tsx
<aside
  className="chrome-scroll"
  style={{
    width: 240,
    borderRight: "1px solid var(--card-border)",
    padding: 12,
    background: "var(--sidebar)",
    color: "var(--chrome-ink)",
    overflowY: "auto",
    flexShrink: 0,
  }}
>
```

Also fix `var(--border)` → `var(--card-border)` in the aside border if not already done.

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/components/Sidebar.tsx frontend/src/components/DiscoveryFiltersSidebar.tsx
git commit -m "feat(ui): chrome scrollbar — dark thumb for sidebar + discovery filter panel"
```

---

### Task 11: Button.tsx — radius + weight + hover

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`

- [ ] **Step 1: Update Button component**

Replace the full content of `frontend/src/components/ui/Button.tsx`:

```tsx
import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
}

const SIZE_STYLE: Record<ButtonSize, { padding: string; fontSize: string }> = {
  sm: { padding: "6px 12px", fontSize: "13px" },
  md: { padding: "8px 16px", fontSize: "14px" },
};

const VARIANT_STYLE: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: "var(--accent)",
    color: "#fff",
    border: "1px solid var(--accent)",
  },
  outline: {
    background: "transparent",
    color: "var(--accent)",
    border: "1px solid var(--accent)",
  },
  ghost: {
    background: "transparent",
    color: "var(--ink)",
    border: "1px solid var(--card-border)",
  },
  danger: {
    background: "var(--error)",
    color: "#fff",
    border: "1px solid var(--error)",
  },
};

const HOVER_STYLE: Record<ButtonVariant, React.CSSProperties> = {
  primary: { opacity: 0.88 },
  outline: { background: "var(--accent-tint)" },
  ghost: { background: "var(--canvas-bg)", borderColor: "var(--card-border-strong)" },
  danger: { opacity: 0.88 },
};

export function Button({
  variant = "primary",
  size = "md",
  iconLeft,
  iconRight,
  style,
  type = "button",
  disabled,
  children,
  onMouseEnter,
  onMouseLeave,
  ...rest
}: ButtonProps) {
  const variantStyle = VARIANT_STYLE[variant];
  const sizeStyle = SIZE_STYLE[size];

  function handleMouseEnter(e: React.MouseEvent<HTMLButtonElement>) {
    if (!disabled) {
      const hover = HOVER_STYLE[variant];
      Object.assign(e.currentTarget.style, hover);
    }
    onMouseEnter?.(e);
  }

  function handleMouseLeave(e: React.MouseEvent<HTMLButtonElement>) {
    if (!disabled) {
      // Reset to base variant styles
      e.currentTarget.style.opacity = "1";
      e.currentTarget.style.background = (variantStyle.background as string) ?? "transparent";
      e.currentTarget.style.borderColor = (variantStyle.border as string)?.split(" ").pop() ?? "";
    }
    onMouseLeave?.(e);
  }

  return (
    <button
      type={type}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        borderRadius: "var(--radius)",
        fontWeight: 600,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        transition: "background .15s, color .15s, border-color .15s, opacity .15s",
        ...sizeStyle,
        ...variantStyle,
        ...style,
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/Button.tsx
git commit -m "feat(ui): Button — radius 8px, font-weight 600, hover states"
```

---

### Task 12: CollapsibleSection.tsx — padding + icon box

**Files:**
- Modify: `frontend/src/components/CollapsibleSection.tsx`

- [ ] **Step 1: Update prominent section styles**

Find the prominent branch (around line 40). Update the button style:

```tsx
style={{
  background: "var(--card-bg)",
  border: "1px solid var(--card-border)",
  borderRadius: open ? "var(--radius) var(--radius) 0 0" : "var(--radius)",
  width: "100%",
  textAlign: "left",
  display: "flex",
  alignItems: "center",
  gap: 10,
  padding: "11px 16px",        // was 9px 12px
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: "var(--ink-subtle)",
  cursor: "pointer",
  transition: "background .12s",
  fontFamily: "inherit",
}}
onMouseEnter={(e) => { e.currentTarget.style.background = "var(--canvas-bg)"; }}
onMouseLeave={(e) => { e.currentTarget.style.background = "var(--card-bg)"; }}
```

Update icon box style:
```tsx
{icon && (
  <span style={{
    width: 26,
    height: 26,
    borderRadius: 8,
    background: "var(--accent-tint)",
    border: "1px solid var(--accent-border)",
    color: "var(--accent)",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  }}>
    {icon}
  </span>
)}
```

Update the open body wrapper:
```tsx
<div style={{
  background: "var(--card-bg)",
  border: "1px solid var(--card-border)",
  borderTop: "none",
  borderRadius: "0 0 var(--radius) var(--radius)",
  padding: "14px 16px",
}}>
```

Wrap the whole prominent section in a `<section>` with shadow:
```tsx
<section style={{ marginBottom: 16, boxShadow: "var(--shadow-card)", borderRadius: "var(--radius)" }}>
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CollapsibleSection.tsx
git commit -m "feat(ui): CollapsibleSection — larger padding, icon border, hover, shadow"
```

---

### Task 13: Source link cards (TopicCard + TopicDetail)

**Files:**
- Modify: `frontend/src/components/TopicCard.tsx`
- Modify: `frontend/src/components/TopicDetail.tsx`

- [ ] **Step 1: Add hostnameOf helper to TopicCard.tsx**

TopicCard.tsx defines its own local icons but no hostname helper. Add before the component:

```tsx
function hostnameOf(url: string): string {
  try { return new URL(url).hostname; } catch { return ""; }
}
```

- [ ] **Step 2: Update item links in TopicCard expanded sources**

Find the `items.map((it) => (` inside the expanded `open` section. Replace the `<a>` element:

```tsx
{items.map((it) => (
  <a
    key={it.id}
    href={safeHref(it.canonical_url)}
    target="_blank"
    rel="noreferrer noopener"
    onClick={(e) => e.stopPropagation()}
    style={{
      display: "flex",
      gap: 12,
      alignItems: "center",
      padding: "10px 12px",
      background: "var(--card-bg)",
      border: "1px solid var(--card-border)",
      borderRadius: 8,
      marginBottom: 6,
      textDecoration: "none",
      color: "var(--ink)",
      transition: "border-color .15s, box-shadow .15s",
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.borderColor = "var(--card-border-strong)";
      e.currentTarget.style.boxShadow = "0 2px 8px rgba(28,25,23,.06)";
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.borderColor = "var(--card-border)";
      e.currentTarget.style.boxShadow = "none";
    }}
  >
    {it.image_url && (
      <img
        src={it.image_url}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        style={{
          width: 44, height: 44, objectFit: "cover",
          borderRadius: 8, flexShrink: 0, background: "var(--canvas-bg)",
        }}
      />
    )}
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: "var(--accent)", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 2 }}>
        {hostnameOf(it.canonical_url)}
      </div>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
        {it.title}
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-subtle)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {it.canonical_url}
      </div>
    </div>
    <ExternalLinkIcon style={{ color: "var(--ink-subtle)", flexShrink: 0 }} />
  </a>
))}
```

Also add ExternalLinkIcon to the import from `"./ui/icons"` in TopicCard.tsx.

- [ ] **Step 3: Update source items in TopicDetail.tsx**

In `TopicDetail.tsx`, find the `group.map((it, idx) => (` section (the items within each domain group). Update the item row to show the title as a card-style link:

```tsx
<a
  href={safeHref(it.canonical_url)}
  target="_blank"
  rel="noreferrer noopener"
  style={{
    display: "block",
    fontWeight: 500,
    color: "var(--accent)",
    textDecoration: "none",
    fontSize: 14,
    marginBottom: 2,
  }}
  onMouseEnter={(e) => { e.currentTarget.style.textDecoration = "underline"; }}
  onMouseLeave={(e) => { e.currentTarget.style.textDecoration = "none"; }}
>
  {it.title}
  {" "}<ExternalLinkIcon width={11} height={11} style={{ display: "inline", verticalAlign: "middle", color: "var(--ink-subtle)" }} />
</a>
```

Add ExternalLinkIcon to TopicDetail.tsx import from `"./ui/icons"`. Also change image borderRadius in TopicDetail items from `4` to `8`.

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TopicCard.tsx frontend/src/components/TopicDetail.tsx
git commit -m "feat(ui): source link cards — card wrapper, domain label, ExternalLinkIcon"
```

---

### Task 14: Section labels + canvas padding + article title

**Files:**
- Modify: `frontend/src/components/TopicDetail.tsx`
- Modify: `frontend/src/components/ArticleView.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update h3 section headers in TopicDetail.tsx to label-tag style**

Find the two `<h3>` elements for "Źródła" and "Źródła streamowe":

```tsx
// Replace both with:
<div style={{
  fontSize: 10, fontWeight: 700, letterSpacing: ".12em", textTransform: "uppercase",
  color: "var(--accent)", marginTop: 24, marginBottom: 10,
  display: "flex", alignItems: "center", gap: 6,
}}>
  <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent)", flexShrink: 0 }} />
  {t.discovery.topic.sources} ({detail.items.length})
</div>
```

For stream sources header, adjust the count accordingly.

- [ ] **Step 2: Update ArticleView metadata card title typography**

In `ArticleView.tsx`, find the `<h2>` inside the metadata card (around line 211):

```tsx
// Replace:
<h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>{article.topic}</h2>

// With:
<h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-.025em", marginBottom: 6 }}>{article.topic}</h2>
```

- [ ] **Step 3: Verify canvas area padding in App.tsx**

Open `frontend/src/App.tsx`. Find the canvas scroll area that wraps ArticleView (the div with `flex: 1, overflowY: "auto"`). Ensure it has padding:

```tsx
style={{ flex: 1, overflowY: "auto", padding: "28px 36px" }}
```

If it doesn't have explicit padding, add it. If the ArticleView itself has internal padding that achieves the same, leave it and just confirm visually.

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TopicDetail.tsx frontend/src/components/ArticleView.tsx frontend/src/App.tsx
git commit -m "feat(ui): section labels accent style, article title typography, canvas padding"
```

### Task 15: DateRangePicker.tsx — token fix + modal shadow + radius

**Files:**
- Modify: `frontend/src/components/DateRangePicker.tsx`

- [ ] **Step 1: Replace legacy tokens in inline styles**

In `DateRangePicker.tsx`, find-and-replace in the inline style props (NOT inside the `<style>` CSS string — handle those in step 2):

```
"var(--white)"   →  "var(--card-bg)"
"var(--border)"  →  "var(--card-border)"
"var(--muted)"   →  "var(--ink-subtle)"
"var(--text)"    →  "var(--ink)"
"var(--sidebar)" →  "var(--canvas-bg)"
```

This covers: popover root `background` (L183), popover `border` (L184), left rail `borderRight`/`borderBottom` (L254–255), narrow preset button `border` active/inactive (L280), preset button `color` (L283), bottom bar `borderTop` (L319), bottom bar `background` (L325), clear button `color` (L332), cancel button `border` + `color` (L352–355). For the Apply button `color: "var(--white)"` at L365 change to `"#fff"` directly (accent button always dark bg).

- [ ] **Step 2: Replace legacy tokens inside the `<style>` CSS string**

Inside the `<style>{`...`}</style>` block (lines ~196–247), replace:

```
var(--muted)  →  var(--ink-subtle)
var(--text)   →  var(--ink)
var(--white)  →  #fff
```

This fixes: navigation button color, weekday header color, day button base color, disabled/outside day color, and the range-start/end selected button text color.

- [ ] **Step 3: Upgrade shadow + border-radius on popover root**

Find the popover root div (the one with `position: "fixed"`, `zIndex: 1000`). Update three properties:

```tsx
// Change:
border: "1px solid var(--border)",
borderRadius: "var(--radius)",
boxShadow: "0 8px 24px rgba(0,0,0,0.08)",

// To:
border: "1px solid var(--card-border)",
borderRadius: "var(--radius-lg)",
boxShadow: "var(--shadow-modal)",
```

- [ ] **Step 4: Apply button font-weight**

Find the Apply button (line ~362). Change `fontWeight: 500` → `fontWeight: 600`.

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/DateRangePicker.tsx
git commit -m "feat(ui): DateRangePicker — token fix, modal shadow, radius-lg"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| Discovery tabs → pills | Task 3 |
| Filter sidebar custom styled | Task 4 |
| TopicCard → cards + chips | Task 5 |
| TopicDetail token fix + meta card | Task 1 |
| NewArticleForm token fix | Task 2 |
| Icon containers (meta row) | Task 6 |
| Emoji → SVG | Task 6 |
| Modal overlay blur + shadow | Task 7 |
| Running state framing | Task 8 |
| Sidebar two-line layout | Task 9 |
| Chrome scrollbar | Task 10 |
| Button radius + hover | Task 11 |
| CollapsibleSection padding + icon | Task 12 |
| Source link cards | Task 13 |
| Section labels + typography | Task 14 |
| DateRangePicker token fix + shadow | Task 15 |
| RadioIcon, ExternalLinkIcon added | Task 6 |

All spec requirements covered. ✓

### Placeholder scan

No TBD, no "similar to Task N" shortcuts, all code blocks complete. ✓

### Type consistency

- `ExternalLinkIcon` added in Task 6 (`icons.tsx`), used in Task 13 (`TopicCard.tsx`, `TopicDetail.tsx`) — consistent.
- `RadioIcon` added in Task 6, used in Task 6 — same task, consistent.
- `PlayIcon` added in Task 6, used in Task 6 — same task, consistent.
- `MetaIconBox` defined and used in Task 6 — same task.
- `hostnameOf` added to `TopicCard.tsx` in Task 13 — defined before use.
- `filterBtn`, `filterBtnActive`, `sectionLabel` in Task 4 — defined before use in JSX.
- Button `HOVER_STYLE` object keys match `VARIANT_STYLE` keys — all 4 variants present. ✓
