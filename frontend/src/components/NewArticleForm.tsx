// frontend/src/components/NewArticleForm.tsx
import { useState } from "react";
import { useArticles } from "../lib/useArticles";
import { useAuth } from "../lib/useAuth";
import { useT } from "../i18n";
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

interface NewArticleFormProps {
  onCreated: (articleId: string) => void;
}

function SubSection({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{ background: "none", border: "none", fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 5, cursor: "pointer", padding: "4px 0" }}
      >
        <span style={{ fontSize: 9 }}>{open ? "▼" : "▶"}</span>
        {label}
      </button>
      {open && <div style={{ marginTop: 10, paddingLeft: 12 }}>{children}</div>}
    </div>
  );
}

export function NewArticleForm({ onCreated }: NewArticleFormProps) {
  const { submitArticle } = useArticles();
  const { user } = useAuth();
  const t = useT();
  const na = t.newArticle;

  const [topic, setTopic] = useState("");
  const [instructions, setInstructions] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Agent model overrides (separate from domain_overrides because scraping needs field remapping)
  const [agentModels, setAgentModels] = useState<Record<string, string>>({});
  const [agentFallbacks, setAgentFallbacks] = useState<Record<string, string>>({});

  // Generic domain_overrides dict — keys match DomainConfigUpdate field names
  const [ov, setOv] = useState<Record<string, unknown>>({});

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
      setOv((prev) => { const { [key]: _, ...rest } = prev; return rest; });
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

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 10px",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    fontSize: 13,
    fontFamily: "var(--font)",
    background: "var(--white)",
    color: "var(--text)",
  };

  const labelSt: React.CSSProperties = { display: "block", fontSize: 12, marginBottom: 4, color: "var(--muted)" };
  const sm = { ...inputStyle, fontSize: 12 };

  return (
    <div style={{ maxWidth: 620 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>{na.heading}</h2>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.topicLabel}</label>
          <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder={na.topicPlaceholder} required style={inputStyle} />
        </div>

        <div>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.instructionsLabel}</label>
          <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} placeholder={na.instructionsPlaceholder} style={{ ...inputStyle, resize: "vertical" }} />
        </div>

        <div>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.urlsLabel}</label>
          <textarea value={urlsText} onChange={(e) => setUrlsText(e.target.value)} rows={3} placeholder={na.urlsPlaceholder} style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace" }} />
        </div>

        {/* Advanced */}
        <div>
          <button
            type="button"
            onClick={() => setAdvancedOpen((o) => !o)}
            style={{ background: "none", border: "none", fontSize: 13, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}
          >
            <span style={{ fontSize: 10 }}>{advancedOpen ? "▼" : "▶"}</span>
            {na.advanced}
          </button>

          {advancedOpen && (
            <div style={{ marginTop: 12, paddingLeft: 12, display: "flex", flexDirection: "column", gap: 6, borderLeft: "2px solid var(--border)" }}>
              <p style={{ fontSize: 11, color: "var(--muted)", margin: "0 0 4px" }}>{na.advancedHint}</p>

              {/* Models */}
              <SubSection label={na.sectionModels}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
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
              </SubSection>

              {/* Search */}
              <SubSection label={na.sectionSearch}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
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
              </SubSection>

              {/* Media search */}
              <SubSection label={na.sectionMedia}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, marginBottom: 10 }}>
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
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
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
              </SubSection>

              {/* Guidelines */}
              <SubSection label={na.sectionGuidelines}>
                <textarea rows={8} placeholder={na.guidelinesPlaceholder}
                  style={{ ...sm, resize: "vertical", fontFamily: "monospace", fontSize: 11 }}
                  onChange={(e) => set("guidelines", e.target.value)} />
              </SubSection>

              {/* HTML format */}
              <SubSection label={na.sectionHtml}>
                <textarea rows={6} placeholder={na.htmlPlaceholder}
                  style={{ ...sm, resize: "vertical", fontFamily: "monospace", fontSize: 11 }}
                  onChange={(e) => set("html_format", e.target.value)} />
              </SubSection>

              {/* Reviewer */}
              <SubSection label={na.sectionReviewer}>
                <label style={{ display: "block", fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                  {na.reviewerRounds}
                </label>
                <input type="number" min={1} max={5} defaultValue={1} style={{ ...sm, width: 60, marginBottom: 10 }}
                  onChange={(e) => {
                    const v = Math.max(1, Math.min(5, +e.target.value));
                    if (v !== 1) set("reflection_rounds", v); else set("reflection_rounds", null);
                  }} />
                <label style={{ display: "block", fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                  {na.reviewerInstructions}
                </label>
                <textarea rows={4} placeholder={na.reviewerInstructionsPlaceholder}
                  style={{ ...sm, resize: "vertical", fontFamily: "monospace", fontSize: 11 }}
                  onChange={(e) => set("reflection_stance", e.target.value)} />
              </SubSection>

              {/* Example H1s */}
              <SubSection label={na.sectionTitles}>
                <ExampleList
                  placeholder={na.titlePlaceholder}
                  addLabel={na.addButton}
                  onChange={(titles) => set("example_titles", titles.length ? titles : null)}
                  inputStyle={sm}
                />
              </SubSection>

              {/* Example articles */}
              <SubSection label={na.sectionArticles}>
                <ExampleList
                  placeholder={na.articlePlaceholder}
                  addLabel={na.addButton}
                  rows={3}
                  onChange={(articles) => set("example_articles", articles.length ? articles : null)}
                  inputStyle={sm}
                />
              </SubSection>
            </div>
          )}
        </div>

        {error && <p style={{ color: "#ef4444", fontSize: 13 }}>{error}</p>}

        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={loading || !topic.trim()}
          style={{ alignSelf: "flex-start" }}
        >
          {loading ? na.generating : na.generate}
        </Button>
      </form>
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
              style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 12, flexShrink: 0, paddingTop: 6 }}>
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
