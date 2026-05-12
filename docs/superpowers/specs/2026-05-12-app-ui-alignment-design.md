# App UI Alignment — Design Spec
**Date:** 2026-05-12  
**Goal:** Align the authenticated app's design language with the landing page and pitch deck — same typography, icon treatment, card system, color system.

---

## Problem

The app uses the correct CSS token system but doesn't apply the landing page's design language consistently:
- Flat list rows instead of card components with border-radius + shadow
- Raw inline SVGs (13px, no container) instead of icon-in-box treatment
- `<details>/<summary>` with browser disclosure triangles instead of custom styled filter sidebar
- Tabs with borders on inactive state instead of pill navigation
- Light scrollbar thumb on dark chrome backgrounds
- Chips without solid borders (rgba background only)
- Modals without backdrop-filter and deep shadow
- Emoji characters instead of SVG icons
- 27 legacy token occurrences (`var(--white)`, `var(--border)`, `var(--muted)`, `var(--text)`) in NewArticleForm + TopicDetail

---

## Design Tokens (reference)

```
--accent: #ea580c          --accent-tint: #fff7ed      --accent-border: #fed7aa
--accent-lt: rgba(234,88,12,.12)
--canvas-bg: #fafaf9       --card-bg: #ffffff          --card-border: #e7e5e4
--card-border-strong: #d4d0cc
--chrome-bg: #0d1117       --chrome-bg2: #111827       --chrome-border: #1f2937
--chrome-ink: #f9fafb      --chrome-muted: #9ca3af     --chrome-faint: #4b5563
--shadow-card: 0 1px 2px rgba(28,25,23,.04), 0 1px 3px rgba(28,25,23,.06)
--shadow-card-hover: 0 4px 16px rgba(28,25,23,.08)
--shadow-modal: 0 24px 64px rgba(13,17,23,.25)
--radius: 8px              --radius-lg: 10px
```

---

## Components + Changes

### Sidebar article list (NEW — added from user feedback)

**Current:** One-line title (ellipsis), status dot left of title, date + MINE chip inline.

**Target layout:**
```
[Title line 1                    ]
[Title line 2 if needed          ]
[● status-dot  date  MINE-chip   ]
```

- Title: `font-size: 13px`, `font-weight: 600`, `line-clamp: 2` (webkit), `letter-spacing: -.01em`
- Status row below title: `display: flex; gap: 6px; align-items: center; margin-top: 5px`
- Status dot: same colors as now (`running`=warning, `done`=✓ green check, `failed`=red ✕)
- Date: `font-size: 11px`, `color: var(--chrome-muted)`
- MINE chip: pill, `border-radius: 999px`, `padding: 1px 7px`, `font-size: 10px`, `font-weight: 600`, `background: rgba(234,88,12,.12)`, `border: 1px solid var(--accent-border)`, `color: var(--accent-light)`
- Remove `white-space: nowrap; text-overflow: ellipsis` from title div
- Remove the leading dot/indicator column; dot moves to meta row
- Increase item `padding: 10px 12px → 11px 14px`
- Selected item: left border 3px accent + `var(--accent-lt)` background (unchanged)

### Discovery tab bar (DiscoveryHub.tsx)

**Target:** Pill navigation, no border on inactive.

```css
/* active */
background: var(--accent); color: #fff; border-radius: 999px; border: none; font-weight: 600;

/* inactive */
background: transparent; color: var(--ink-subtle); border-radius: 999px; border: none;
/* hover: background: var(--canvas-bg); color: var(--ink); */
```

- Icon treatment: wrap each tab icon in `18×18px` span, `border-radius: 5px`, `background: rgba(255,255,255,.2)` for active, `background: var(--accent-lt)` for inactive.
- Tab bar background: `var(--card-bg)`, `border-bottom: 1px solid var(--card-border)`, `padding: 10px 20px`.
- Sort `<select>`: `appearance: none`, custom chevron SVG, `box-shadow: var(--shadow-card)`, padding-right for arrow.

### Discovery filter sidebar (DiscoveryFiltersSidebar.tsx)

Replace `<details>/<summary>` with custom collapsible using `useState`.

**Section label style:**
```css
font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
color: var(--accent); display: flex; align-items: center; gap: 7px;
padding: 4px 0 8px; border-bottom: 1px solid var(--chrome-border);
cursor: pointer;
/* dot prefix via ::before: width:5px; height:5px; background:currentColor; border-radius:50% */
/* chevron on right, rotates on open */
```

**Filter button style:**
```css
/* inactive */
background: transparent; border: none; border-radius: 6px; color: var(--chrome-muted);
padding: 5px 8px; font-size: 13px; transition: background .12s, color .12s;
/* hover: background: rgba(255,255,255,.05); color: var(--chrome-ink); */

/* active */
background: rgba(234,88,12,.12); color: var(--accent-light); font-weight: 600;
```

Status indicators: replace `●`/`○` characters with proper `8px` colored dots using `background:` CSS.

### TopicCard (TopicCard.tsx)

- Outer wrapper: `padding: 8px 12px` (wraps cards), `background: var(--canvas-bg)`
- Each card: `border: 1px solid var(--card-border)`, `border-radius: 12px`, `box-shadow: var(--shadow-card)`, `padding: 16px 20px`, `margin-bottom: 8px`
- Hover: `box-shadow: var(--shadow-card-hover)`, `border-color: var(--card-border-strong)`
- Token fix: `var(--white)→var(--card-bg)`, `var(--border)→var(--card-border)`, `var(--muted)→var(--ink-subtle)`, `var(--text)→var(--ink)`
- Chips: `background: var(--accent-tint)`, `border: 1px solid var(--accent-border)`, `font-weight: 600` for accent; analogous solid borders for success/error.
- Section label "sources": landing label tag style (accent, 10px, uppercase, .12em, dot prefix)
- Meta-row icons: each in `28×28px` span, `border-radius: 7px`, `background: var(--accent-tint)`, `color: var(--accent)`, inner SVG 14px

### TopicDetail (TopicDetail.tsx)

- Token fix: same as TopicCard
- Source group header: `background: var(--canvas-bg)`, text `color: var(--ink)`, border `var(--card-border)`
- Right `<aside>` meta: wrap in card (`background: var(--card-bg)`, border, `border-radius: 10px`, `padding: 16px 20px`)
- Meta rows: label `font-size: 10px; text-transform: uppercase; letter-spacing: .1em; color: var(--ink-subtle)` + value below
- h3 section headers: landing label tag style

### NewArticleForm (NewArticleForm.tsx)

- Token fix: 27 occurrences of `var(--white)→var(--card-bg)`, `var(--border)→var(--card-border)`
- Modal overlay: `rgba(13,17,23,.65)` + `backdrop-filter: blur(4px)`
- Modal box: `box-shadow: var(--shadow-modal)`, `border-radius: 14px`
- Modal title: `font-weight: 800`, `letter-spacing: -.025em`

### Button (Button.tsx)

- `border-radius`: `var(--radius-lg)` → `var(--radius)` (10px → 8px)
- `font-weight`: 500 → 600
- Ghost variant: `border: 1px solid var(--card-border)` (was `var(--border)` — same now, kept for clarity)
- Add hover via `onMouseEnter`/`onMouseLeave` (existing pattern): primary → `opacity: .9`, ghost → `background: var(--canvas-bg)`

### CollapsibleSection (CollapsibleSection.tsx)

- Prominent header: `padding: 9px 12px → 11px 16px`
- Icon box: `24px → 26px`, add `border: 1px solid var(--accent-border)`
- Header hover: `background: var(--canvas-bg)`
- Whole section: `box-shadow: var(--shadow-card)`

### Scrollbars (tokens.css)

Add dark scrollbar for chrome areas:
```css
.chrome-scroll::-webkit-scrollbar { width: 4px; height: 4px; }
.chrome-scroll::-webkit-scrollbar-track { background: transparent; }
.chrome-scroll::-webkit-scrollbar-thumb { background: var(--chrome-border); border-radius: 2px; }
.chrome-scroll::-webkit-scrollbar-thumb:hover { background: var(--chrome-faint); }
```

Apply `.chrome-scroll` to sidebar `overflowY: auto` div and DiscoveryFiltersSidebar `aside`.

### Running state (ArticleView.tsx)

Wrap spinner + label in:
```css
display: flex; align-items: center; gap: 10px;
padding: 10px 16px; border-radius: var(--radius);
background: var(--warning-lt); border: 1px solid rgba(217,119,6,.3);
color: var(--warning-fg); font-size: 13px;
```

### Source links (TopicCard expanded, TopicDetail)

Each source item:
```css
display: flex; gap: 12px; align-items: center;
padding: 10px 12px; border: 1px solid var(--card-border); border-radius: 8px;
background: var(--canvas-bg); margin-bottom: 6px;
transition: border-color .15s, box-shadow .15s;
```
- Domain label: `font-size: 11px; font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: .04em`
- Replace `↗` with SVG ExternalLinkIcon
- Thumbnail: `border-radius: 8px` (from 4px)

### Emoji → SVG

Replace in TopicCard.tsx + SocialMediaAttachmentCard.tsx + SocialMediaAttachmentCard:
- `📡` → `RadioIcon` (new SVG — waveform/signal path)
- `📸` → text label "Instagram" styled
- `𝕏` → text label "X.com" styled  
- `⬇`/`⏳` → existing `DownloadIcon` / spinner span
- `▶` → existing pattern or small play SVG

### ArticleView canvas wrapper (App.tsx)

Canvas area padding: verify and set to `padding: 28px 36px` on the scroll container that wraps `ArticleView`.

---

## Implementation Phases

### Phase 1 — Token cleanup (3 files)
Tasks: NewArticleForm legacy tokens, TopicDetail legacy tokens + card wrappers, DiscoveryHub tabBtn legacy tokens + sort select.

### Phase 2 — Discovery redesign (biggest visual win)
Tasks: Tab bar → pills, filter sidebar → custom styled, TopicCard → cards with shadow + crisp chips.

### Phase 3 — Icons & badges
Tasks: Meta-row icon containers (TopicCard), emoji → SVG replacements, stream source badge style.

### Phase 4 — Modals, running state, sidebar layout
Tasks: NewArticleForm + WriteFromTopicDialog modal overlay/shadow, ArticleView running state framing, **Sidebar article item two-line layout**.

### Phase 5 — Polish
Tasks: Scrollbar chrome, Button hover + radius, CollapsibleSection padding, source cards, section labels, canvas padding, mine badge pill.

---

## Per-phase review

After each phase: user runs `npm run dev` locally and visually reviews before proceeding to next phase.
