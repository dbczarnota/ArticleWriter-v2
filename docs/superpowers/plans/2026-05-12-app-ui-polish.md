# App UI Polish — Align with Landing Page Design Language

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the post-login app visually consistent with the headlinesforge.com landing page and pitch deck — same icon containers, section labels, chip shapes, typography, and status affordances.

**Architecture:** Pure CSS/inline-style changes to existing React components. No new abstractions, no new routes. Each task touches 1–2 files and is independently deployable.

**Tech Stack:** React + TypeScript, inline styles, CSS custom properties from `tokens.css`. Pre-commit check: `cd frontend && npx tsc --noEmit`.

---

## Design Reference — Landing vs App Gap

| Element | Landing / Mockup target | Current app |
|---|---|---|
| Filter chips | Pills `border-radius: 999px` | Rounded rect `var(--radius)` = 8px |
| "Mine" tag in sidebar | Tint `rgba(234,88,12,.12)` + `var(--accent-light)` text | Solid orange fill |
| Running status dot | Pulsing CSS animation | Static dot |
| Done state in article header | Green pill + check icon | Raw checkbox + text |
| CollapsibleSection prominent | 11px uppercase label + 24×24 accent-tinted icon square | 13px normal case, no icon |
| Article HTML h1 | 28–30px / 800 weight | unstyled beyond margin |
| Section label pattern | `• LABEL` in accent, 11px uppercase, letter-spacing 0.12em | not used in app |

---

## File Map

| File | What changes |
|---|---|
| `frontend/src/components/Sidebar.tsx` | Filter chips → pills; Mine tag → tint; running dot → pulse |
| `frontend/src/components/ArticleView.tsx` | Done state → green pill with icon |
| `frontend/src/components/CollapsibleSection.tsx` | Add `icon` prop; prominent header → uppercase 11px + icon square |
| `frontend/src/components/ui/icons.tsx` | Add `InfoIcon`, `QuoteIcon`, `TitlesIcon`, `FacebookIcon` |
| `frontend/src/styles/tokens.css` | Add `@keyframes pulse-dot`; improve `.article-html h1/h2/p` typography |

---

## Task 1: Discovery canvas dark-on-dark visibility ✅ DONE (commit fff03e2)

Already fixed in hotfix commit. Documented here for completeness.

- [x] `DiscoveryHub.tsx`: tab bar + sort row `var(--bg2)` → `var(--card-bg)`
- [x] `TopicDetail.tsx`: source group headers + window chips `var(--sidebar)` → canvas tokens
- [x] `git push origin master`

---

## Task 2: Sidebar — pill chips + mine tag tint

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Change filter chips to pills**

Find the three `All / Undone / Done` chip buttons (around line 199) and the `Mine` chip button (around line 212). Change `borderRadius: "var(--radius)"` to `borderRadius: 999` on all four:

```tsx
// All/Undone/Done chips — line ~199
<button key={f} onClick={() => setDoneFilter(f)} style={{
  background: active ? "var(--accent)" : "transparent",
  color: active ? "#fff" : "var(--chrome-muted)",
  border: `1px solid ${active ? "var(--accent)" : "var(--chrome-border)"}`,
  borderRadius: 999,           // ← was: "var(--radius)"
  padding: "3px 8px",
  fontSize: 11,
  fontWeight: 500,
  cursor: "pointer",
}}>{labels[f]}</button>
```

```tsx
// Mine chip — line ~212
<button onClick={() => setOnlyMine((v) => !v)} style={{
  background: onlyMine ? "var(--accent)" : "transparent",
  color: onlyMine ? "#fff" : "var(--chrome-muted)",
  border: `1px solid ${onlyMine ? "var(--accent)" : "var(--chrome-border)"}`,
  borderRadius: 999,           // ← was: "var(--radius)"
  padding: "3px 8px",
  fontSize: 11,
  fontWeight: 500,
  cursor: "pointer",
}}>{t.sidebar.filterMine}</button>
```

- [ ] **Step 2: Mine tag in article list — subtle tint**

Find the `isMine` badge (around line 347) and replace solid orange with subtle tint:

```tsx
{isMine && (
  <span style={{
    background: "rgba(234,88,12,.12)",   // ← was: "var(--accent)"
    color: "var(--accent-light)",         // ← was: "#fff"
    borderRadius: 3,
    padding: "0 4px",
    fontSize: 10,
    fontWeight: 600,
    lineHeight: "16px",
  }}>
    {t.sidebar.mine}
  </span>
)}
```

- [ ] **Step 3: Type-check**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: no output (clean).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "fix(ui): sidebar chips → pills, mine tag → accent tint"
git push origin master
```

---

## Task 3: Running status dot — pulse animation

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Add pulse keyframe to tokens.css**

Append after the existing scrollbar rules (around line 108):

```css
@keyframes pulse-dot {
  0%   { box-shadow: 0 0 0 0 rgba(234,88,12,.6); }
  60%  { box-shadow: 0 0 0 5px rgba(234,88,12,0); }
  100% { box-shadow: 0 0 0 0 rgba(234,88,12,0); }
}
```

- [ ] **Step 2: Apply animation to running dot in Sidebar**

Find the status dot `<span>` for the running state (inside the article item map, around line 330). The running state is when `a.status === "running"` and `!a.marked_done` and `a.status !== "failed"`. The dot uses `STATUS_DOT[a.status]`:

```tsx
<span style={{
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: STATUS_DOT[a.status] ?? "#94a3b8",
  flexShrink: 0,
  marginTop: 5,
  animation: a.status === "running" ? "pulse-dot 1.8s ease-out infinite" : undefined,
}} />
```

- [ ] **Step 3: Type-check + commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/components/Sidebar.tsx
git commit -m "feat(ui): running status dot pulse animation"
git push origin master
```

---

## Task 4: Article header — Done as a green pill

**Files:**
- Modify: `frontend/src/components/ArticleView.tsx`

Replace the raw `<input type="checkbox">` Done control in the metadata section with a styled pill that matches the mockup's `.meta-pill.success` pattern.

- [ ] **Step 1: Import CheckIcon**

`CheckIcon` is already exported from `./ui/icons` and imported in ArticleView (look for `import { CodeIcon, CopyIcon, DownloadIcon } from "./ui/icons"`). Add `CheckIcon` to that import:

```tsx
import { CodeIcon, CopyIcon, DownloadIcon, CheckIcon } from "./ui/icons";
```

- [ ] **Step 2: Replace checkbox + text with pill**

Find the `<label>` element containing the `<input type="checkbox">` around line 224. Replace the entire label with:

```tsx
<button
  onClick={async () => {
    const done = !article.marked_done;
    setArticle((a) => a ? { ...a, marked_done: done } : a);
    try {
      await onMarkDone?.(article.id, done);
    } catch {
      setArticle((a) => a ? { ...a, marked_done: !done } : a);
    }
  }}
  style={{
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "3px 9px",
    background: article.marked_done ? "var(--success-tint)" : "var(--card-bg)",
    border: `1px solid ${article.marked_done ? "#bbf7d0" : "var(--card-border)"}`,
    borderRadius: 999,
    fontSize: 12,
    fontWeight: article.marked_done ? 600 : 400,
    color: article.marked_done ? "var(--success-fg)" : "var(--ink-subtle)",
    cursor: "pointer",
  }}
>
  {article.marked_done && <CheckIcon width={11} height={11} strokeWidth={3} />}
  {article.marked_done ? av.markDone : av.markDone}
  {article.marked_done && article.marked_done_by_name && (
    <span style={{ fontWeight: 400, color: "var(--success-fg)", opacity: 0.7 }}>
      · {article.marked_done_by_name}
    </span>
  )}
</button>
```

- [ ] **Step 3: Type-check + commit**

```bash
git add frontend/src/components/ArticleView.tsx
git commit -m "feat(ui): done state as green pill with check icon"
git push origin master
```

---

## Task 5: CollapsibleSection — icon square + uppercase label

**Files:**
- Modify: `frontend/src/components/CollapsibleSection.tsx`

Add an optional `icon` prop to the prominent variant. When supplied, render a 24×24 accent-tinted icon square before the label. Change label to 11px uppercase style.

- [ ] **Step 1: Update interface and prominent render**

Replace the entire `CollapsibleSection` function with:

```tsx
import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  prominent?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="10" height="10" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.5"
      strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, transition: "transform 0.15s ease", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
      aria-hidden
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function CollapsibleSection({ title, count, defaultOpen = false, prominent = false, icon, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const label = count !== undefined ? `${title} (${count})` : title;

  if (prominent) {
    return (
      <section style={{ marginBottom: 16 }}>
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          style={{
            background: "var(--card-bg)",
            border: "1px solid var(--card-border)",
            borderRadius: open ? "var(--radius) var(--radius) 0 0" : "var(--radius)",
            width: "100%",
            textAlign: "left",
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 12px",
            marginBottom: 0,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--ink-subtle)",
            cursor: "pointer",
          }}
        >
          {icon && (
            <span style={{
              width: 24, height: 24,
              borderRadius: 7,
              background: "var(--accent-tint)",
              color: "var(--accent)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}>
              {icon}
            </span>
          )}
          <span style={{ flex: 1 }}>{label}</span>
          <span style={{ color: "var(--ink-subtle)", display: "inline-flex" }}>
            <Chevron open={open} />
          </span>
        </button>
        {open && (
          <div style={{
            background: "var(--card-bg)",
            border: "1px solid var(--card-border)",
            borderTop: "none",
            borderRadius: "0 0 var(--radius) var(--radius)",
            padding: "12px 14px",
          }}>
            {children}
          </div>
        )}
      </section>
    );
  }

  return (
    <div style={{ marginTop: 16 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          background: "none",
          border: "none",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--ink-muted)",
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 0",
          cursor: "pointer",
        }}
      >
        <Chevron open={open} />
        {label}
      </button>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```powershell
cd frontend; npx tsc --noEmit
```
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CollapsibleSection.tsx
git commit -m "feat(ui): collapsible section prominent — icon square + uppercase label"
git push origin master
```

---

## Task 6: Add section icons + wire to ArticleView

**Files:**
- Modify: `frontend/src/components/ui/icons.tsx`
- Modify: `frontend/src/components/ArticleView.tsx`

- [ ] **Step 1: Add missing icons to icons.tsx**

Append after the last existing icon (`DiscoveryIcon`):

```tsx
export function TitlesIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="15" y2="12" />
      <line x1="3" y1="18" x2="18" y2="18" />
    </svg>
  );
}
export function InfoIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
export function QuoteIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V20c0 1 0 1 1 1z" />
      <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3c0 1 0 1 1 1z" />
    </svg>
  );
}
export function ShareIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...baseProps} {...props}>
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}
```

- [ ] **Step 2: Wire icons to CollapsibleSection calls in ArticleView.tsx**

Update the import line for icons:

```tsx
import { CodeIcon, CopyIcon, DownloadIcon, CheckIcon, TitlesIcon, InfoIcon, QuoteIcon, ShareIcon, GlobeIcon } from "./ui/icons";
```

Then add `icon` prop to each prominent `CollapsibleSection`:

```tsx
// Alternative titles
<CollapsibleSection prominent icon={<TitlesIcon width={13} height={13} />} title={av.altTitles} count={article.alternative_titles.length} defaultOpen>

// Follow-up topics
<CollapsibleSection prominent icon={<DiscoveryIcon width={13} height={13} />} title={av.followupTopics} count={article.followup_topics.length} defaultOpen>

// Facebook teasers
<CollapsibleSection prominent icon={<ShareIcon width={13} height={13} />} title={av.facebookTeasers} count={article.facebook_teasers.length} defaultOpen>

// Social media
<CollapsibleSection prominent icon={<GlobeIcon width={13} height={13} />} title={av.socialMedia} count={...}>
```

Also add `DiscoveryIcon` to the import (it's in the same icons file).

- [ ] **Step 3: Type-check + commit**

```powershell
cd frontend; npx tsc --noEmit
```

```bash
git add frontend/src/components/ui/icons.tsx frontend/src/components/ArticleView.tsx
git commit -m "feat(ui): section icons in ArticleView collapsible headers"
git push origin master
```

---

## Task 7: Article HTML typography — improve .article-html styles

**Files:**
- Modify: `frontend/src/styles/tokens.css`

The article HTML body card should feel like reading a real article. Current styles are minimal.

- [ ] **Step 1: Update .article-html rules in tokens.css**

Replace the existing `.article-html` block (starts around line 111):

```css
/* Article HTML rendered content */
.article-html h1 {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin: 0 0 16px;
  line-height: 1.15;
  color: var(--ink);
}
.article-html h2 {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 28px 0 10px;
  line-height: 1.3;
  color: var(--ink);
}
.article-html h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 20px 0 8px;
  line-height: 1.35;
  color: var(--ink);
}
.article-html p {
  margin: 0 0 14px;
  color: var(--ink-muted);
  line-height: 1.72;
}
.article-html strong {
  color: var(--ink);
  font-weight: 600;
}
.article-html blockquote {
  border-left: 3px solid var(--accent);
  background: var(--accent-tint);
  margin: 20px 0;
  padding: 14px 18px;
  border-radius: 0 var(--radius) var(--radius) 0;
  font-style: italic;
  color: var(--ink);
}
.article-html blockquote p {
  margin: 0;
  color: var(--ink);
}
.article-html a {
  color: var(--accent);
}
.article-html ul,
.article-html ol {
  padding-left: 1.5em;
  margin: 0 0 14px;
  color: var(--ink-muted);
}
.article-html li {
  margin-bottom: 6px;
  line-height: 1.65;
}
```

- [ ] **Step 2: Type-check + commit**

```powershell
cd frontend; npx tsc --noEmit
```

```bash
git add frontend/src/styles/tokens.css
git commit -m "feat(ui): article HTML typography — sizes, weights, line-height"
git push origin master
```

---

## Task 8: DiscoveryFiltersSidebar — canvas token migration

**Files:**
- Modify: `frontend/src/components/DiscoveryFiltersSidebar.tsx`

The sidebar uses `var(--muted)`, `var(--text)`, `var(--sidebar)` legacy tokens. On the canvas these aliases work, but the sidebar itself has `background: "var(--sidebar)"` = chrome dark — correct for the dark left panel. The item buttons use `var(--text)` and `var(--accent)` — verify these look right after the main fixes. If section labels `var(--muted)` are too dark/invisible against chrome, add explicit chrome token.

- [ ] **Step 1: Fix section label color**

In `DiscoveryFiltersSidebar.tsx`, the `labelStyle` (around line 53) uses `color: "var(--muted)"`. Since the sidebar background is `var(--sidebar)` = `var(--chrome-bg2)` = dark, `var(--muted)` = `var(--ink-subtle)` = `#78716c` (dark warm gray) is too dark to see. Change to chrome token:

```tsx
const labelStyle: React.CSSProperties = {
  fontSize: 11,
  textTransform: "uppercase",
  color: "var(--chrome-muted)",    // ← was: "var(--muted)"
  cursor: "pointer",
  letterSpacing: "0.06em",
  fontWeight: 600,
  padding: "4px 0",
};
```

- [ ] **Step 2: Fix button row text color**

The `buttonRow` style (around line 62) uses `color: "var(--text)"`. On dark sidebar, `var(--text)` = `var(--ink)` = `#1c1917` = near-black = invisible. Change to:

```tsx
const buttonRow: React.CSSProperties = {
  ...
  color: "var(--chrome-muted)",    // ← was: "var(--text)"
  ...
};
```

The active state already uses `color: "var(--accent)"` which is fine on dark.

- [ ] **Step 3: Type-check + commit**

```powershell
cd frontend; npx tsc --noEmit
```

```bash
git add frontend/src/components/DiscoveryFiltersSidebar.tsx
git commit -m "fix(ui): discovery sidebar labels use chrome tokens (dark bg)"
git push origin master
```

---

## Deploy

After completing all tasks, trigger deploy:

```bash
gh workflow run "Build & Deploy" --ref master
```
