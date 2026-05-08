// frontend/src/components/NewArticleForm.tsx
import { useEffect, useState } from "react";
import { useArticles } from "../lib/useArticles";
import { useAuth } from "../lib/useAuth";
import { useT } from "../i18n";
import { useFocusTrap } from "../lib/useFocusTrap";
import { AVAILABLE_MODELS } from "./DomainConfigForm";
import { Button } from "./ui/Button";

const MEDIA_KEYS = [
  { key: "youtube_search", label: "YouTube" },
  { key: "twitter_search", label: "Twitter/X" },
  { key: "tiktok_search", label: "TikTok" },
  { key: "instagram_search", label: "Instagram" },
  { key: "reddit_search", label: "Reddit" },
  { key: "news_search", label: "News" },
  { key: "facebook_search", label: "Facebook" },
];

const TAB_IDS = [
  "topic",
  "models",
  "search",
  "media",
  "guidelines",
  "html",
  "reviewer",
  "titles",
  "articles",
] as const;
type TabId = (typeof TAB_IDS)[number];

interface NewArticleFormProps {
  onCreated: (articleId: string) => void;
  onCancel?: () => void;
}

export function NewArticleForm({ onCreated, onCancel }: NewArticleFormProps) {
  const { submitArticle } = useArticles();
  const { user } = useAuth();
  const t = useT();
  const na = t.newArticle;

  const [mode, setMode] = useState<"basic" | "settings">("basic");
  const [activeTab, setActiveTab] = useState<TabId>("topic");
  const [topic, setTopic] = useState("");
  const [instructions, setInstructions] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Agent model overrides (separate from domain_overrides because scraping needs field remapping)
  const [agentModels, setAgentModels] = useState<Record<string, string>>({});
  const [agentFallbacks, setAgentFallbacks] = useState<Record<string, string>>({});

  // Generic domain_overrides dict — keys match DomainConfigUpdate field names
  const [ov, setOv] = useState<Record<string, unknown>>({});

  const dialogRef = useFocusTrap<HTMLDivElement>(true);

  // ESC closes the modal (unless we're submitting).
  useEffect(() => {
    if (!onCancel) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) onCancel?.();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, loading]);

  const AGENT_DEFS = [
    { key: "search", label: t.agents.search },
    { key: "scraping", label: t.agents.scraping },
    { key: "parsing", label: t.agents.parsing },
    { key: "extraction", label: t.agents.extraction },
    { key: "adaptive_search", label: t.agents.adaptive_search },
    { key: "instructions", label: t.agents.instructions },
    { key: "writer", label: t.agents.writer },
    { key: "reflection", label: t.agents.reflection },
    { key: "followup", label: t.agents.followup },
  ];

  const FRESHNESS_OPTIONS = [
    { value: "qdr:h", label: na.freshnessHour },
    { value: "qdr:d", label: na.freshnessDay },
    { value: "qdr:w", label: na.freshnessWeek },
    { value: "qdr:m", label: na.freshnessMonth },
    { value: "qdr:y", label: na.freshnessYear },
  ];

  function set(key: string, value: unknown) {
    if (value === "" || value === null || value === undefined) {
      setOv((prev) => { const next = { ...prev }; delete next[key]; return next; });
    } else {
      setOv((prev) => ({ ...prev, [key]: value }));
    }
  }

  function num(key: string, raw: string, min: number, max: number) {
    if (!raw) { set(key, null); return; }
    const n = parseInt(raw, 10);
    if (!isNaN(n) && n >= min && n <= max) set(key, n);
    else if (!raw) set(key, null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const urls = urlsText.split("\n").map((u) => u.trim()).filter(Boolean);

      const agents: Record<string, Record<string, unknown>> = {};
      const allAgentKeys = new Set([...Object.keys(agentModels), ...Object.keys(agentFallbacks)]);
      for (const key of allAgentKeys) {
        const model = agentModels[key];
        const fallbackStr = agentFallbacks[key] ?? "";
        const fallbacks = fallbackStr.split(",").map((s) => s.trim()).filter(Boolean);
        if (!model && fallbacks.length === 0) continue;
        if (key === "scraping") {
          agents[key] = {
            ...(model ? { filter_model: model } : {}),
            ...(fallbacks.length ? { filter_fallback_models: fallbacks } : {}),
          };
        } else {
          agents[key] = {
            ...(model ? { model } : {}),
            ...(fallbacks.length ? { fallback_models: fallbacks } : {}),
          };
        }
      }

      const author_name =
        [user?.givenName, user?.familyName].filter(Boolean).join(" ") || user?.email || undefined;
      const result = await submitArticle({
        topic: topic.trim(),
        additional_instructions: instructions.trim() || undefined,
        urls: urls.length > 0 ? urls : undefined,
        agents: Object.keys(agents).length > 0 ? agents : undefined,
        domain_overrides: Object.keys(ov).length > 0 ? ov : undefined,
        author_name,
      });
      setLoading(false);
      onCreated(result.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }

  // ── Shared input styles ────────────────────────────────────────────────
  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 10px",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    fontSize: 13,
    fontFamily: "var(--font)",
    background: "var(--white)",
    color: "var(--text)",
    boxSizing: "border-box",
  };
  const labelSt: React.CSSProperties = { display: "block", fontSize: 12, marginBottom: 4, color: "var(--muted)" };
  const sm: React.CSSProperties = { ...inputStyle, fontSize: 12 };

  const tabLabels: Record<TabId, string> = {
    topic: na.tabs.topic,
    models: na.tabs.models,
    search: na.tabs.search,
    media: na.tabs.media,
    guidelines: na.tabs.guidelines,
    html: na.tabs.html,
    reviewer: na.tabs.reviewer,
    titles: na.tabs.titles,
    articles: na.tabs.articles,
  };

  // ── Reusable field blocks ──────────────────────────────────────────────
  const TopicFields = (
    <>
      <div>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.topicLabel}</label>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={na.topicPlaceholder} required style={inputStyle} />
      </div>
      <div style={{ marginTop: 14 }}>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.instructionsLabel}</label>
        <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} placeholder={na.instructionsPlaceholder} style={{ ...inputStyle, resize: "vertical" }} />
      </div>
      <div style={{ marginTop: 14 }}>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.urlsLabel}</label>
        <textarea value={urlsText} onChange={(e) => setUrlsText(e.target.value)} rows={3} placeholder={na.urlsPlaceholder} style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace" }} />
      </div>
    </>
  );

  function renderTab(id: TabId) {
    switch (id) {
      case "topic":
        return TopicFields;
      case "models":
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {AGENT_DEFS.map(({ key, label }) => (
              <div key={key} style={{ display: "grid", gridTemplateColumns: "150px 1fr 1fr", gap: 6, alignItems: "center" }}>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{label}</span>
                <select value={agentModels[key] ?? ""} onChange={(e) => setAgentModels((m) => ({ ...m, [key]: e.target.value }))} style={sm}>
                  <option value="">{na.defaultModel}</option>
                  {AVAILABLE_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
                <input value={agentFallbacks[key] ?? ""} onChange={(e) => setAgentFallbacks((f) => ({ ...f, [key]: e.target.value }))} placeholder={na.fallbacksPlaceholder} style={{ ...sm, fontSize: 11, fontFamily: "monospace" }} />
              </div>
            ))}
          </div>
        );
      case "search":
        return (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div>
              <label style={labelSt}>{na.searchFreshness}</label>
              <select value={(ov.search_freshness as string) ?? ""} onChange={(e) => set("search_freshness", e.target.value)} style={sm}>
                <option value="">{na.defaultFreshness}</option>
                {FRESHNESS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label style={labelSt}>{na.articleLength}</label>
              <input type="number" placeholder={na.articleLengthPlaceholder} min={100} max={5000} style={sm}
                onChange={(e) => num("target_word_count", e.target.value, 100, 5000)} />
            </div>
            <div>
              <label style={labelSt}>{na.numQueries}</label>
              <input type="number" placeholder={na.numQueriesPlaceholder} min={1} max={10} style={sm}
                onChange={(e) => num("num_queries", e.target.value, 1, 10)} />
            </div>
            <div>
              <label style={labelSt}>{na.maxResults}</label>
              <input type="number" placeholder={na.maxResultsPlaceholder} min={1} max={20} style={sm}
                onChange={(e) => num("max_results", e.target.value, 1, 20)} />
            </div>
            <div>
              <label style={labelSt}>{na.maxFacts}</label>
              <input type="number" placeholder={na.maxFactsPlaceholder} min={1} max={50} style={sm}
                onChange={(e) => num("max_facts", e.target.value, 1, 50)} />
            </div>
            <div>
              <label style={labelSt}>{na.maxQuotes}</label>
              <input type="number" placeholder={na.maxQuotesPlaceholder} min={0} max={20} style={sm}
                onChange={(e) => num("max_quotes", e.target.value, 0, 20)} />
            </div>
            <div>
              <label style={labelSt}>{na.minSourceSignals}</label>
              <input type="number" placeholder={na.minSourceSignalsPlaceholder} min={0} max={20} style={sm}
                onChange={(e) => num("min_source_signals", e.target.value, 0, 20)} />
            </div>
            <div>
              <label style={labelSt}>{na.maxPages}</label>
              <input type="number" placeholder={na.maxPagesPlaceholder} min={1} max={50} style={sm}
                onChange={(e) => num("max_pages_to_scrape", e.target.value, 1, 50)} />
            </div>
            <div>
              <label style={labelSt}>{na.contextArticles}</label>
              <input type="number" placeholder={na.contextArticlesPlaceholder} min={0} max={10} style={sm}
                onChange={(e) => num("reflection_context_articles", e.target.value, 0, 10)} />
            </div>
          </div>
        );
      case "media":
        return (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 14 }}>
              {MEDIA_KEYS.map(({ key, label }) => (
                <div key={key}>
                  <label style={labelSt}>{label}</label>
                  <select value={(ov[key] as string) ?? ""} onChange={(e) => set(key, e.target.value === "" ? null : e.target.value === "true")} style={sm}>
                    <option value="">{na.defaultMedia}</option>
                    <option value="true">{na.yes}</option>
                    <option value="false">{na.no}</option>
                  </select>
                </div>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <label style={labelSt}>{na.mediaLanguages}</label>
                <input placeholder={na.mediaLanguagesPlaceholder} style={sm}
                  onChange={(e) => {
                    const v = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                    set("media_search_languages", v.length ? v : null);
                  }} />
              </div>
              <div>
                <label style={labelSt}>{na.mediaNumResults}</label>
                <input type="number" placeholder={na.mediaNumResultsPlaceholder} min={1} max={20} style={sm}
                  onChange={(e) => num("media_search_num", e.target.value, 1, 20)} />
              </div>
              <div>
                <label style={labelSt}>{na.mediaMaxTiers}</label>
                <input type="number" placeholder={na.mediaMaxTiersPlaceholder} min={1} max={5} style={sm}
                  onChange={(e) => num("media_search_max_query_tiers", e.target.value, 1, 5)} />
              </div>
              <div style={{ display: "flex", alignItems: "flex-end", paddingBottom: 4 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                  <input type="checkbox" style={{ accentColor: "var(--accent)" }}
                    onChange={(e) => set("youtube_sort_by_date", e.target.checked)} />
                  {na.youtubeSortByDate}
                </label>
              </div>
            </div>
          </>
        );
      case "guidelines":
        return (
          <textarea rows={16} placeholder={na.guidelinesPlaceholder}
            style={{ ...sm, resize: "vertical", fontFamily: "monospace", fontSize: 12, minHeight: 320 }}
            onChange={(e) => set("guidelines", e.target.value)} />
        );
      case "html":
        return (
          <textarea rows={14} placeholder={na.htmlPlaceholder}
            style={{ ...sm, resize: "vertical", fontFamily: "monospace", fontSize: 12, minHeight: 320 }}
            onChange={(e) => set("html_format", e.target.value)} />
        );
      case "reviewer":
        return (
          <>
            <label style={labelSt}>{na.reviewerRounds}</label>
            <input type="number" min={1} max={5} defaultValue={1} style={{ ...sm, width: 80, marginBottom: 14 }}
              onChange={(e) => {
                const v = Math.max(1, Math.min(5, +e.target.value));
                if (v !== 1) set("reflection_rounds", v); else set("reflection_rounds", null);
              }} />
            <label style={labelSt}>{na.reviewerInstructions}</label>
            <textarea rows={10} placeholder={na.reviewerInstructionsPlaceholder}
              style={{ ...sm, resize: "vertical", fontFamily: "monospace", fontSize: 12, minHeight: 220 }}
              onChange={(e) => set("reflection_stance", e.target.value)} />
          </>
        );
      case "titles":
        return (
          <ExampleList
            placeholder={na.titlePlaceholder}
            addLabel={na.addButton}
            onChange={(titles) => set("example_titles", titles.length ? titles : null)}
            inputStyle={sm}
          />
        );
      case "articles":
        return (
          <ExampleList
            placeholder={na.articlePlaceholder}
            addLabel={na.addButton}
            rows={3}
            onChange={(articles) => set("example_articles", articles.length ? articles : null)}
            inputStyle={sm}
          />
        );
    }
  }

  // ── Modal shell ────────────────────────────────────────────────────────
  const isSettings = mode === "settings";
  const maxWidth = isSettings ? 920 : 560;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(28, 25, 23, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: 16,
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-article-title"
        style={{
          background: "var(--white)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          width: "100%",
          maxWidth,
          maxHeight: "90vh",
          height: isSettings ? "min(640px, 85vh)" : "auto",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          transition: "max-width 0.18s ease",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <header
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <h3 id="new-article-title" style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>
            {isSettings ? na.headingSettings : na.heading}
          </h3>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={loading}
              style={{
                background: "none",
                border: 0,
                color: "var(--muted)",
                fontSize: 22,
                cursor: loading ? "default" : "pointer",
                padding: 0,
                lineHeight: 1,
              }}
              aria-label="Close"
            >
              ×
            </button>
          )}
        </header>

        <form
          onSubmit={handleSubmit}
          style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}
        >
          {isSettings ? (
            // ── Settings mode: sidebar tabs + active panel ───────────────
            <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
              <nav
                style={{
                  width: 200,
                  flexShrink: 0,
                  borderRight: "1px solid var(--border)",
                  paddingTop: 8,
                  overflowY: "auto",
                }}
              >
                {TAB_IDS.map((id) => {
                  const active = activeTab === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setActiveTab(id)}
                      style={{
                        display: "block",
                        width: "100%",
                        padding: "8px 12px",
                        textAlign: "left",
                        background: active ? "var(--accent-lt)" : "none",
                        borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
                        borderTop: "none",
                        borderRight: "none",
                        borderBottom: "none",
                        fontSize: 13,
                        fontWeight: active ? 500 : 400,
                        color: active ? "var(--accent)" : "var(--text)",
                        cursor: "pointer",
                        borderRadius: "0 var(--radius) var(--radius) 0",
                      }}
                    >
                      {tabLabels[id]}
                    </button>
                  );
                })}
              </nav>
              <div
                style={{
                  flex: 1,
                  padding: "20px 24px",
                  overflowY: "auto",
                  minWidth: 0,
                }}
              >
                {activeTab !== "topic" && (
                  <p style={{ fontSize: 11, color: "var(--muted)", margin: "0 0 12px" }}>
                    {na.advancedHint}
                  </p>
                )}
                {renderTab(activeTab)}
              </div>
            </div>
          ) : (
            // ── Basic mode: three fields stacked ─────────────────────────
            <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
              {TopicFields}
            </div>
          )}

          {error && (
            <div
              style={{
                padding: "8px 20px",
                borderTop: "1px solid var(--border)",
                background: "var(--error-lt)",
                color: "var(--error-fg)",
                fontSize: 12,
                wordBreak: "break-word",
              }}
            >
              {error}
            </div>
          )}

          <footer
            style={{
              padding: "12px 20px",
              borderTop: "1px solid var(--border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 8,
            }}
          >
            <button
              type="button"
              onClick={() => setMode(isSettings ? "basic" : "settings")}
              disabled={loading}
              style={{
                background: "none",
                border: "none",
                color: "var(--muted)",
                fontSize: 13,
                cursor: loading ? "default" : "pointer",
                padding: "4px 0",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--muted)"; }}
            >
              {isSettings ? na.backToBasic : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                  {na.settingsButton}
                </>
              )}
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              {onCancel && (
                <Button variant="ghost" size="md" onClick={onCancel} disabled={loading} type="button">
                  {na.cancel}
                </Button>
              )}
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={loading || !topic.trim()}
              >
                {loading ? na.generating : na.generate}
              </Button>
            </div>
          </footer>
        </form>
      </div>
    </div>
  );
}

// Minimal dynamic list (add/remove rows) for example_titles / example_articles.
function ExampleList({ placeholder, addLabel, rows = 1, onChange, inputStyle }: {
  placeholder: string;
  addLabel: string;
  rows?: number;
  onChange: (values: string[]) => void;
  inputStyle: React.CSSProperties;
}) {
  const [items, setItems] = useState<string[]>([""]);

  function update(i: number, v: string) {
    const next = items.map((x, idx) => idx === i ? v : x);
    setItems(next);
    onChange(next.filter(Boolean));
  }

  function remove(i: number) {
    const next = items.filter((_, idx) => idx !== i);
    const safe = next.length ? next : [""];
    setItems(safe);
    onChange(safe.filter(Boolean));
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((val, i) => (
        <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
          {rows > 1
            ? <textarea value={val} onChange={(e) => update(i, e.target.value)} rows={rows} placeholder={placeholder} style={{ ...inputStyle, flex: 1, resize: "vertical" }} />
            : <input value={val} onChange={(e) => update(i, e.target.value)} placeholder={placeholder} style={{ ...inputStyle, flex: 1 }} />
          }
          {items.length > 1 && (
            <button type="button" onClick={() => remove(i)}
              style={{ background: "none", border: "none", color: "var(--error)", cursor: "pointer", fontSize: 12, flexShrink: 0, paddingTop: 6 }}>
              ✕
            </button>
          )}
        </div>
      ))}
      <button type="button" onClick={() => setItems((p) => [...p, ""])}
        style={{ background: "none", border: "none", fontSize: 12, color: "var(--accent)", cursor: "pointer", textAlign: "left", padding: 0 }}>
        {addLabel}
      </button>
    </div>
  );
}
