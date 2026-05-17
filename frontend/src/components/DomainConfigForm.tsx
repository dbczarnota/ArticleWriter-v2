// frontend/src/components/DomainConfigForm.tsx
// TODO(tests): expand frontend test coverage to all components — NewArticleForm, ArticleView, SettingsView, Sidebar, CollapsibleSection
import { useEffect, useState } from "react";
import type { DomainConfigData } from "../types";
import { useT } from "../i18n";
import { useApi } from "../lib/useApi";

type MediaTipKey = "youtube" | "twitter" | "tiktok" | "instagram" | "reddit" | "news" | "facebook";

const MEDIA_TOGGLES: Array<{ key: keyof DomainConfigData; label: string; tipKey: MediaTipKey }> = [
  { key: "youtube_search", label: "YouTube", tipKey: "youtube" },
  { key: "twitter_search", label: "Twitter/X", tipKey: "twitter" },
  { key: "tiktok_search", label: "TikTok", tipKey: "tiktok" },
  { key: "instagram_search", label: "Instagram", tipKey: "instagram" },
  { key: "reddit_search", label: "Reddit", tipKey: "reddit" },
  { key: "news_search", label: "News", tipKey: "news" },
  { key: "facebook_search", label: "Facebook", tipKey: "facebook" },
];

export const AVAILABLE_MODELS = [
  { id: "google-gla:gemini-pro-latest", label: "Gemini Pro Latest" },
  { id: "google-gla:gemini-flash-latest", label: "Gemini Flash Latest" },
  { id: "google-gla:gemini-flash-lite-latest", label: "Gemini Flash Lite Latest" },
  { id: "groq:openai/gpt-oss-120b", label: "Groq OSS 120B (fast/cheap)" },
];

type AgentKey = "search" | "scraping" | "parsing" | "extraction" | "adaptive_search" | "instructions" | "writer" | "reflection" | "followup" | "media_search" | "media_extraction" | "stream_analysis" | "stream_digest";

const DEFAULT_MODEL_PER_AGENT: Record<AgentKey, string> = {
  search:           "google-gla:gemini-flash-latest",
  scraping:         "google-gla:gemini-flash-latest",
  parsing:          "google-gla:gemini-flash-latest",
  extraction:       "google-gla:gemini-flash-latest",
  adaptive_search:  "google-gla:gemini-flash-latest",
  instructions:     "google-gla:gemini-pro-latest",
  writer:           "google-gla:gemini-pro-latest",
  reflection:       "google-gla:gemini-flash-latest",
  followup:         "google-gla:gemini-pro-latest",
  media_search:     "google-gla:gemini-flash-lite-latest",
  media_extraction: "google-gla:gemini-flash-latest",
  stream_analysis:  "google-gla:gemini-flash-lite-latest",
  stream_digest:    "google-gla:gemini-flash-latest",
};

const DEFAULT_FALLBACK = "google-gla:gemini-flash-latest";

const FIXED_FRESHNESS = new Set(["qdr:d", "qdr:w", "qdr:m", "qdr:y"]);

// Small tooltip icon — shows a floating box on hover.
function Tip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex", verticalAlign: "middle", marginLeft: 4 }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 14, height: 14, borderRadius: "50%",
        background: "var(--border)", color: "var(--muted)", fontSize: 9,
        cursor: "help", userSelect: "none", lineHeight: 1, flexShrink: 0,
      }}>?</span>
      {show && (
        <div style={{
          position: "absolute", left: 0, top: "calc(100% + 5px)",
          background: "#1e293b", color: "#f1f5f9", fontSize: 11,
          borderRadius: 5, padding: "7px 10px", width: 260,
          zIndex: 1000, lineHeight: 1.55, pointerEvents: "none",
          boxShadow: "0 4px 16px rgba(0,0,0,.25)",
          whiteSpace: "normal",
        }}>
          {text}
        </div>
      )}
    </span>
  );
}

function CustomCheckbox({ checked }: { checked: boolean }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      width: 15, height: 15, flexShrink: 0,
      borderRadius: 3,
      background: checked ? "var(--accent)" : "transparent",
      border: checked ? "1.5px solid var(--accent)" : "1.5px solid var(--border)",
      transition: "background .12s, border-color .12s",
    }}>
      {checked && (
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="1.5 5 4 7.5 8.5 2.5" />
        </svg>
      )}
    </span>
  );
}

const DOMAIN_RE = /^[a-z0-9.-]+\.[a-z]{2,}$/;

interface SourceDomainListFieldProps {
  label: string;
  hint: string;
  value: string[];
  max: number;
  onChange: (next: string[]) => void;
  counterTemplate: string;
  overLimitText: string;
  invalidTemplate: string;
  inputStyle: React.CSSProperties;
  labelStyle: React.CSSProperties;
}

function SourceDomainListField({ label, hint, value, max, onChange, counterTemplate, overLimitText, invalidTemplate, inputStyle, labelStyle }: SourceDomainListFieldProps) {
  const safeValue = Array.isArray(value) ? value : [];
  const [text, setText] = useState<string>(() => safeValue.join("\n"));

  const lines = text.split("\n").map((l) => l.trim().toLowerCase()).filter(Boolean);
  const invalid = lines.filter((l) => l.startsWith("http://") || l.startsWith("https://") || l.includes("/") || l.includes(":") || !DOMAIN_RE.test(l));
  const dedup: string[] = [];
  const seen = new Set<string>();
  for (const l of lines) {
    if (!seen.has(l)) {
      seen.add(l);
      dedup.push(l);
    }
  }
  const overLimit = dedup.length > max;
  const counter = counterTemplate.replace("{count}", String(dedup.length)).replace("{max}", String(max));

  function handleBlur() {
    if (invalid.length > 0 || overLimit) return;
    const same = dedup.length === safeValue.length && dedup.every((d, i) => d === safeValue[i]);
    if (!same) onChange(dedup);
  }

  return (
    <label style={{ ...labelStyle, marginBottom: 20, display: "block" }}>
      {label}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlur}
        rows={6}
        style={{
          ...inputStyle,
          resize: "vertical",
          fontFamily: "monospace",
          borderColor: overLimit || invalid.length > 0 ? "var(--error, #c33)" : (inputStyle.border as string | undefined)?.includes("var(--border)") ? "var(--border)" : undefined,
        }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginTop: 4 }}>
        <span style={{ color: "var(--muted)" }}>{hint}</span>
        <span style={{ color: overLimit ? "var(--error, #c33)" : "var(--muted)", fontWeight: overLimit ? 600 : 400 }}>{counter}</span>
      </div>
      {overLimit && (
        <div style={{ fontSize: 12, color: "var(--error, #c33)", marginTop: 4 }}>{overLimitText}</div>
      )}
      {invalid.length > 0 && (
        <div style={{ fontSize: 12, color: "var(--error, #c33)", marginTop: 4 }}>
          {invalid.slice(0, 3).map((d) => invalidTemplate.replace("{value}", d)).join(" · ")}
        </div>
      )}
    </label>
  );
}

interface DomainConfigFormProps {
  initialConfig: DomainConfigData;
  activeSection: string;
  saving: boolean;
  error: string | null;
  onSave: (config: DomainConfigData) => void;
}

export function DomainConfigForm({ initialConfig, activeSection, saving, error, onSave }: DomainConfigFormProps) {
  const t = useT();
  const dc = t.domainConfig;
  const { request } = useApi();
  const [form, setForm] = useState<DomainConfigData>(initialConfig);
  const [icToggling, setIcToggling] = useState(false);
  const [icError, setIcError] = useState<string | null>(null);

  async function toggleImageCreator(enable: boolean) {
    setIcToggling(true);
    setIcError(null);
    try {
      const { enabled } = await request<{ enabled: boolean }>(
        `/v2/tools/image-creator/${enable ? "enable" : "disable"}`,
        { method: "POST" },
      );
      setForm((f) => ({ ...f, image_creator_enabled: enabled }));
    } catch (e) {
      setIcError(e instanceof Error ? e.message : "Toggle failed");
    } finally {
      setIcToggling(false);
    }
  }

  const FRESHNESS_OPTIONS = [
    { value: "qdr:d", label: dc.freshnessDay },
    { value: "qdr:w", label: dc.freshnessWeek },
    { value: "qdr:m", label: dc.freshnessMonth },
    { value: "qdr:y", label: dc.freshnessYear },
  ];

  const AGENT_DEFINITIONS: Array<{ key: AgentKey; label: string; tip: string }> = [
    { key: "search", label: t.agents.search, tip: t.agentTips.search },
    { key: "scraping", label: t.agents.scraping, tip: t.agentTips.scraping },
    { key: "parsing", label: t.agents.parsing, tip: t.agentTips.parsing },
    { key: "extraction", label: t.agents.extraction, tip: t.agentTips.extraction },
    { key: "adaptive_search", label: t.agents.adaptive_search, tip: t.agentTips.adaptive_search },
    { key: "instructions", label: t.agents.instructions, tip: t.agentTips.instructions },
    { key: "writer", label: t.agents.writer, tip: t.agentTips.writer },
    { key: "reflection", label: t.agents.reflection, tip: t.agentTips.reflection },
    { key: "followup", label: t.agents.followup, tip: t.agentTips.followup },
    { key: "media_search", label: t.agents.media_search, tip: t.agentTips.media_search },
    { key: "media_extraction", label: t.agents.media_extraction, tip: t.agentTips.media_extraction },
    { key: "stream_analysis", label: t.agents.stream_analysis, tip: t.agentTips.stream_analysis },
    { key: "stream_digest", label: t.agents.stream_digest, tip: t.agentTips.stream_digest },
  ];

  useEffect(() => {
    setForm(initialConfig);
  }, [initialConfig]);

  function set<K extends keyof DomainConfigData>(key: K, value: DomainConfigData[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function sectionVisible(id: string) {
    return activeSection === id;
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

  const labelStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    fontSize: 12,
    fontWeight: 500,
    marginBottom: 4,
    color: "var(--muted)",
  };

  return (
    <div style={{ flex: 1 }}>
      <div style={{ paddingBottom: 80 }}>
        {/* Podstawowe */}
        <section id="podstawowe" style={{ display: sectionVisible("podstawowe") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>{dc.sectionBasic}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={labelStyle}>
                {dc.domainName}
                <Tip text={dc.domainNameHint} />
              </label>
              <input value={form.domain_name} onChange={(e) => set("domain_name", e.target.value)} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.domainDescription}
                <Tip text={dc.tipDescription} />
              </label>
              <textarea value={form.description} onChange={(e) => set("description", e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical" }} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.articleLanguage}
                <Tip text={dc.tipLanguage} />
              </label>
              <input value={form.language} onChange={(e) => set("language", e.target.value)} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.targetWordCount}
                <Tip text={dc.tipTargetWordCount} />
              </label>
              <input type="number" value={form.target_word_count} onChange={(e) => set("target_word_count", +e.target.value)} min={100} max={5000} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Wyszukiwanie */}
        <section id="wyszukiwanie" style={{ display: sectionVisible("wyszukiwanie") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>{dc.sectionSearch}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>
                {dc.searchFreshness}
                <Tip text={dc.tipSearchFreshness} />
              </label>
              {(() => {
                const isCustom = !FIXED_FRESHNESS.has(form.search_freshness);
                const customDays = isCustom ? (parseInt(form.search_freshness.replace("qdr:", "")) || 7) : 7;
                return (
                  <>
                    <select
                      value={isCustom ? "__custom__" : form.search_freshness}
                      onChange={(e) => set("search_freshness", e.target.value === "__custom__" ? `qdr:${customDays}` : e.target.value)}
                      style={inputStyle}
                    >
                      {FRESHNESS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      <option value="__custom__">{dc.freshnessCustom}</option>
                    </select>
                    {isCustom && (
                      <input
                        type="number"
                        value={customDays}
                        min={1}
                        max={365}
                        onChange={(e) => set("search_freshness", `qdr:${Math.max(1, +e.target.value)}`)}
                        style={{ ...inputStyle, marginTop: 6 }}
                        placeholder={dc.customDaysPlaceholder}
                      />
                    )}
                  </>
                );
              })()}
            </div>
            <div>
              <label style={labelStyle}>
                {dc.numQueries}
                <Tip text={dc.tipNumQueries} />
              </label>
              <input type="number" value={form.num_queries} onChange={(e) => set("num_queries", +e.target.value)} min={1} max={10} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.maxResultsPerQuery}
                <Tip text={dc.tipMaxResultsPerQuery} />
              </label>
              <input type="number" value={form.max_results} onChange={(e) => set("max_results", +e.target.value)} min={1} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.minSourceSignals}
                <Tip text={dc.tipMinSourceSignals} />
              </label>
              <input type="number" value={form.min_source_signals} onChange={(e) => set("min_source_signals", +e.target.value)} min={0} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.maxPagesToScrape}
                <Tip text={dc.tipMaxPagesToScrape} />
              </label>
              <input type="number" value={form.max_pages_to_scrape} onChange={(e) => set("max_pages_to_scrape", +e.target.value)} min={1} max={50} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.maxFacts}
                <Tip text={dc.tipMaxFacts} />
              </label>
              <input type="number" value={form.max_facts} onChange={(e) => set("max_facts", +e.target.value)} min={1} max={50} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.maxQuotes}
                <Tip text={dc.tipMaxQuotes} />
              </label>
              <input type="number" value={form.max_quotes} onChange={(e) => set("max_quotes", +e.target.value)} min={0} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.contextArticles}
                <Tip text={dc.tipContextArticles} />
              </label>
              <input type="number" value={form.reflection_context_articles} onChange={(e) => set("reflection_context_articles", +e.target.value)} min={0} max={10} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Źródła — whitelist + blacklist domen */}
        <section id="zrodla" style={{ display: sectionVisible("zrodla") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{dc.sourcesSectionTitle}</h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>{dc.sourcesSectionHint}</p>

          <SourceDomainListField
            label={dc.sourceWhitelist}
            hint={dc.sourceWhitelistHint}
            value={form.source_whitelist}
            max={40}
            onChange={(v) => set("source_whitelist", v)}
            counterTemplate={dc.sourceCounter}
            overLimitText={dc.sourceOverLimit}
            invalidTemplate={dc.sourceInvalidDomain}
            inputStyle={inputStyle}
            labelStyle={labelStyle}
          />

          <SourceDomainListField
            label={dc.sourceBlacklist}
            hint={dc.sourceBlacklistHint}
            value={form.source_blacklist}
            max={20}
            onChange={(v) => set("source_blacklist", v)}
            counterTemplate={dc.sourceCounter}
            overLimitText={dc.sourceOverLimit}
            invalidTemplate={dc.sourceInvalidDomain}
            inputStyle={inputStyle}
            labelStyle={labelStyle}
          />
        </section>

        {/* Media search */}
        <section id="media" style={{ display: sectionVisible("media") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
            {dc.sectionMedia}
            <Tip text={dc.tipMediaSection} />
          </h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>{dc.mediaHint}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {MEDIA_TOGGLES.map(({ key, label, tipKey }) => (
              <label
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 12px",
                  background: form[key] ? "var(--accent-lt)" : "var(--card-bg)",
                  border: `1px solid ${form[key] ? "var(--accent)" : "var(--card-border)"}`,
                  borderRadius: "var(--radius)",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                <input type="checkbox" checked={form[key] as boolean} onChange={(e) => set(key, e.target.checked as DomainConfigData[typeof key])} style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} />
                <CustomCheckbox checked={form[key] as boolean} />
                {label}
                <Tip text={t.mediaTips[tipKey]} />
              </label>
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
            <div>
              <label style={labelStyle}>
                {dc.mediaLanguages}
                <Tip text={dc.tipMediaLanguages} />
              </label>
              <input
                value={form.media_search_languages.join(", ")}
                onChange={(e) => set("media_search_languages", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
                placeholder="en, pl"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.mediaNumResults}
                <Tip text={dc.tipMediaNumResults} />
              </label>
              <input type="number" value={form.media_search_num} onChange={(e) => set("media_search_num", +e.target.value)} min={1} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.mediaMaxTiers}
                <Tip text={dc.tipMediaMaxTiers} />
              </label>
              <input type="number" value={form.media_search_max_query_tiers} onChange={(e) => set("media_search_max_query_tiers", +e.target.value)} min={1} max={5} style={inputStyle} />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer", paddingTop: 20 }}>
              <input type="checkbox" checked={form.youtube_sort_by_date} onChange={(e) => set("youtube_sort_by_date", e.target.checked)} style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} />
              <CustomCheckbox checked={form.youtube_sort_by_date} />
              {dc.youtubeSortByDate}
              <Tip text={dc.tipYoutubeSortByDate} />
            </label>
          </div>
        </section>

        {/* Wybór modeli */}
        <section id="modele" style={{ display: sectionVisible("modele") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{dc.sectionModels}</h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>{dc.modelsHint}</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {AGENT_DEFINITIONS.map(({ key, label, tip }) => (
              <div key={key} style={{ display: "grid", gridTemplateColumns: "200px 1fr 1fr", gap: 8, alignItems: "center" }}>
                <label style={{ ...labelStyle, marginBottom: 0 }}>
                  {label}
                  <Tip text={tip} />
                </label>
                <select
                  value={form.agent_models[key] ?? ""}
                  onChange={(e) => set("agent_models", { ...form.agent_models, [key]: e.target.value })}
                  style={inputStyle}
                >
                  <option value="">{AVAILABLE_MODELS.find((m) => m.id === DEFAULT_MODEL_PER_AGENT[key])?.label ?? DEFAULT_MODEL_PER_AGENT[key]} ({dc.defaultModel})</option>
                  {AVAILABLE_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
                <div style={{ position: "relative" }}>
                  <input
                    value={(form.agent_fallback_models[key] ?? []).join(", ")}
                    onChange={(e) => {
                      const vals = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                      set("agent_fallback_models", { ...form.agent_fallback_models, [key]: vals });
                    }}
                    placeholder={DEFAULT_FALLBACK}
                    style={{ ...inputStyle, fontSize: 12, fontFamily: "monospace" }}
                  />
                  <span style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)" }}>
                    <Tip text={dc.tipFallbacks} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Wytyczne redakcyjne */}
        <section id="wytyczne" style={{ display: sectionVisible("wytyczne") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.sectionGuidelines}
            <Tip text={dc.tipGuidelines} />
          </h3>
          <textarea
            value={form.guidelines}
            onChange={(e) => set("guidelines", e.target.value)}
            rows={12}
            placeholder={dc.guidelinesPlaceholder}
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Format HTML */}
        <section id="html" style={{ display: sectionVisible("html") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.sectionHtml}
            <Tip text={dc.tipHtmlFormat} />
          </h3>
          <textarea
            value={form.html_format}
            onChange={(e) => set("html_format", e.target.value)}
            rows={10}
            placeholder={dc.htmlPlaceholder}
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Recenzent */}
        <section id="stance" style={{ display: sectionVisible("stance") ? "block" : "none", marginBottom: 32 }}>
          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>
              {dc.reviewerRounds}
              <Tip text={dc.tipReviewerRounds} />
            </label>
            <input
              type="number"
              value={form.reflection_rounds}
              onChange={(e) => set("reflection_rounds", Math.max(1, Math.min(5, +e.target.value)))}
              min={1}
              max={5}
              style={{ ...inputStyle, width: 80 }}
            />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.reviewerInstructions}
            <Tip text={dc.tipReviewerInstructions} />
          </h3>
          <textarea
            value={form.reflection_stance}
            onChange={(e) => set("reflection_stance", e.target.value)}
            rows={6}
            placeholder={dc.reviewerInstructionsHint}
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Przykładowe H1 */}
        <section id="tytuly" style={{ display: sectionVisible("tytuly") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.sectionTitles}
            <Tip text={dc.tipExampleTitles} />
          </h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>{dc.titlesHint}</p>
          {form.example_titles.map((text, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
              <input
                value={text}
                onChange={(e) => {
                  const updated = [...form.example_titles];
                  updated[i] = e.target.value;
                  set("example_titles", updated);
                }}
                placeholder={`${dc.titlePlaceholder} ${i + 1}`}
                style={{ ...inputStyle, flex: 1 }}
              />
              <button
                type="button"
                onClick={() => set("example_titles", form.example_titles.filter((_, j) => j !== i))}
                style={{ background: "none", border: "none", fontSize: 13, color: "var(--error)", cursor: "pointer", flexShrink: 0 }}
              >
                {dc.removeTitle}
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("example_titles", [...form.example_titles, ""])}
            style={{
              padding: "6px 14px",
              background: "none",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            {dc.addTitle}
          </button>
        </section>

        {/* Przykładowe artykuły */}
        <section id="przyklady" style={{ display: sectionVisible("przyklady") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.sectionArticles}
            <Tip text={dc.tipExampleArticles} />
          </h3>
          {form.example_articles.map((text, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{dc.articleLabel} {i + 1}</span>
                <button
                  type="button"
                  onClick={() => set("example_articles", form.example_articles.filter((_, j) => j !== i))}
                  style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer" }}
                >
                  {dc.removeTitle}
                </button>
              </div>
              <textarea
                value={text}
                onChange={(e) => {
                  const updated = [...form.example_articles];
                  updated[i] = e.target.value;
                  set("example_articles", updated);
                }}
                rows={8}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("example_articles", [...form.example_articles, ""])}
            style={{
              padding: "6px 14px",
              background: "none",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            {dc.addArticle}
          </button>
        </section>

        {/* Szablony artykułów */}
        <section id="szablony" style={{ display: sectionVisible("szablony") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.sectionTemplates}
            <Tip text={dc.tipTemplates} />
          </h3>
          {(form.article_templates ?? []).map((tmpl, i) => (
            <div key={tmpl.id} style={{ marginBottom: 16, padding: "12px 14px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 8 }}>
                <input
                  value={tmpl.name}
                  onChange={(e) => {
                    const updated = [...(form.article_templates ?? [])];
                    updated[i] = { ...updated[i], name: e.target.value };
                    set("article_templates", updated);
                  }}
                  placeholder={dc.templateNamePlaceholder}
                  style={{ ...inputStyle, fontWeight: 500, flex: 1 }}
                />
                <button
                  type="button"
                  onClick={() => set("article_templates", (form.article_templates ?? []).filter((_, j) => j !== i))}
                  style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", flexShrink: 0 }}
                >
                  {dc.removeTemplate}
                </button>
              </div>
              <textarea
                value={tmpl.body}
                onChange={(e) => {
                  const updated = [...(form.article_templates ?? [])];
                  updated[i] = { ...updated[i], body: e.target.value };
                  set("article_templates", updated);
                }}
                placeholder={dc.templateBodyPlaceholder}
                rows={5}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
              />
              <label style={{ display: "block", fontSize: 12, color: "var(--muted)", margin: "8px 0 4px" }}>
                {dc.templateImageInstructions}
              </label>
              <textarea
                value={tmpl.image_instructions ?? ""}
                onChange={(e) => {
                  const updated = [...(form.article_templates ?? [])];
                  updated[i] = { ...updated[i], image_instructions: e.target.value };
                  set("article_templates", updated);
                }}
                placeholder={dc.templateImageInstructionsPlaceholder}
                rows={2}
                style={{ ...inputStyle, resize: "vertical", fontSize: 12 }}
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("article_templates", [
              { id: crypto.randomUUID(), name: "", body: "", image_instructions: "" },
              ...(form.article_templates ?? []),
            ])}
            style={{
              padding: "6px 14px",
              background: "none",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            {dc.addTemplate}
          </button>
        </section>

        {/* Szablony obrazków */}
        <section id="szablony-obrazkow" style={{ display: sectionVisible("szablony-obrazkow") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
            {dc.imageTemplates ?? "Szablony obrazków"}
          </h3>

          <div style={{ marginBottom: 16, padding: "12px 14px", background: "var(--card-bg)", border: "1px solid var(--card-border)", borderRadius: "var(--radius-lg)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>
                {form.image_creator_enabled ? "Image Creator: włączony" : "Image Creator: wyłączony"}
              </span>
              <span style={{ fontSize: 11, color: "var(--ink-subtle)" }}>
                Pierwsze włączenie automatycznie tworzy klucz API w htmltomedia dla tej organizacji.
              </span>
              {icError && (
                <span style={{ fontSize: 11, color: "var(--error-fg)", wordBreak: "break-word" }}>{icError}</span>
              )}
            </div>
            <button
              type="button"
              disabled={icToggling}
              onClick={() => toggleImageCreator(!form.image_creator_enabled)}
              style={{
                padding: "6px 14px",
                background: form.image_creator_enabled ? "var(--error-lt)" : "var(--accent)",
                color: form.image_creator_enabled ? "var(--error-fg)" : "white",
                border: form.image_creator_enabled ? "1px solid var(--error)" : "none",
                borderRadius: "var(--radius)",
                fontSize: 12,
                fontWeight: 600,
                cursor: icToggling ? "not-allowed" : "pointer",
                opacity: icToggling ? 0.6 : 1,
                fontFamily: "inherit",
                flexShrink: 0,
              }}
            >
              {icToggling ? "..." : (form.image_creator_enabled ? "Wyłącz" : "Włącz")}
            </button>
          </div>

          {!form.image_creator_enabled && (
            <p style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic", padding: "16px 0" }}>
              Włącz Image Creator, aby dodawać i edytować szablony obrazków.
            </p>
          )}

          {form.image_creator_enabled && (form.image_templates ?? []).map((tmpl, i) => (
            <div
              key={tmpl.id}
              style={{ marginBottom: 16, padding: "12px 14px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 8 }}>
                <input
                  value={tmpl.name}
                  onChange={(e) => {
                    const updated = [...(form.image_templates ?? [])];
                    updated[i] = { ...updated[i], name: e.target.value };
                    set("image_templates", updated);
                  }}
                  placeholder="Nazwa szablonu"
                  style={{ ...inputStyle, fontWeight: 500, flex: 1 }}
                />
                <button
                  type="button"
                  onClick={() => set("image_templates", (form.image_templates ?? []).filter((_, j) => j !== i))}
                  style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", flexShrink: 0 }}
                >
                  Usuń
                </button>
              </div>
              <textarea
                value={tmpl.html}
                onChange={(e) => {
                  const updated = [...(form.image_templates ?? [])];
                  updated[i] = { ...updated[i], html: e.target.value };
                  set("image_templates", updated);
                }}
                placeholder="Wklej HTML szablonu z placeholderami {{TEXT:label}} i {{IMAGE:label}}"
                rows={8}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
              />
            </div>
          ))}
          {form.image_creator_enabled && (
            <button
              type="button"
              onClick={() =>
                set("image_templates", [
                  { id: crypto.randomUUID(), name: "", html: "" },
                  ...(form.image_templates ?? []),
                ])
              }
              style={{ padding: "6px 14px", background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: 13, cursor: "pointer" }}
            >
              + Dodaj szablon
            </button>
          )}
        </section>

        {/* Integracje — webhook */}
        <section id="integracje" style={{ display: sectionVisible("integracje") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{dc.webhookSectionTitle}</h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>{dc.webhookSectionHint}</p>

          <label style={labelStyle}>
            {dc.webhookUrl}
            <input
              type="url"
              value={form.webhook_url ?? ""}
              onChange={(e) => set("webhook_url", e.target.value || null)}
              placeholder={dc.webhookUrlPlaceholder}
              style={inputStyle}
            />
          </label>

          <label style={labelStyle}>
            {dc.webhookSecret}
            <input
              type="password"
              value={form.webhook_secret ?? ""}
              onChange={(e) => set("webhook_secret", e.target.value || null)}
              placeholder={dc.webhookSecretPlaceholder}
              autoComplete="off"
              style={inputStyle}
            />
          </label>
        </section>

        {/* Discovery */}
        <section id="discovery" style={{ display: sectionVisible("discovery") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{dc.sectionDiscovery}</h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>{dc.discoveryHint}</p>

          {/* Master switch */}
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              background: form.discovery_enabled ? "var(--accent-lt)" : "var(--card-bg)",
              border: `1px solid ${form.discovery_enabled ? "var(--accent)" : "var(--card-border)"}`,
              borderRadius: "var(--radius)",
              cursor: "pointer",
              fontSize: 13,
              marginBottom: 20,
              width: "fit-content",
            }}
          >
            <input type="checkbox" checked={form.discovery_enabled} onChange={(e) => set("discovery_enabled", e.target.checked)} style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} />
            <CustomCheckbox checked={form.discovery_enabled} />
            {dc.discoveryEnabled}
            <Tip text={dc.tipDiscoveryEnabled} />
          </label>

          {/* Window + threshold */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 24 }}>
            <div>
              <label style={labelStyle}>
                {dc.discoveryTopicMatchingWindow}
                <Tip text={dc.tipDiscoveryTopicMatchingWindow} />
              </label>
              <input
                type="number"
                value={form.discovery_topic_matching_window_days}
                onChange={(e) => set("discovery_topic_matching_window_days", +e.target.value)}
                min={1}
                max={90}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.discoveryFollowupThreshold}
                <Tip text={dc.tipDiscoveryFollowupThreshold} />
              </label>
              <input
                type="number"
                value={form.discovery_followup_threshold}
                onChange={(e) => set("discovery_followup_threshold", +e.target.value)}
                min={1}
                max={100}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>
                {dc.discoveryRetentionDays}
                <Tip text={dc.tipDiscoveryRetentionDays} />
              </label>
              <input
                type="number"
                value={form.discovery_retention_days}
                onChange={(e) => set("discovery_retention_days", +e.target.value)}
                min={1}
                max={365}
                style={inputStyle}
              />
            </div>
          </div>

          {/* Feeds */}
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.discoveryFeeds}
            <Tip text={dc.tipDiscoveryFeeds} />
          </h4>
          {form.discovery_feeds.length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 100px auto",
                gap: 8,
                marginBottom: 4,
                fontSize: 11,
                color: "var(--muted)",
                fontWeight: 500,
              }}
            >
              <span>{dc.discoveryFeedUrl}</span>
              <span>{dc.discoveryFeedName}</span>
              <span>{dc.discoveryFeedInterval}</span>
              <span></span>
            </div>
          )}
          {form.discovery_feeds.map((feed, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 100px auto", gap: 8, marginBottom: 8, alignItems: "center" }}>
              <input
                value={feed.url}
                onChange={(e) => {
                  const updated = [...form.discovery_feeds];
                  updated[i] = { ...feed, url: e.target.value };
                  set("discovery_feeds", updated);
                }}
                placeholder={dc.discoveryFeedUrlPlaceholder}
                style={inputStyle}
              />
              <input
                value={feed.name}
                onChange={(e) => {
                  const updated = [...form.discovery_feeds];
                  updated[i] = { ...feed, name: e.target.value };
                  set("discovery_feeds", updated);
                }}
                placeholder={dc.discoveryFeedName}
                style={inputStyle}
              />
              <input
                type="number"
                value={feed.poll_interval_min}
                onChange={(e) => {
                  const updated = [...form.discovery_feeds];
                  updated[i] = { ...feed, poll_interval_min: Math.max(1, +e.target.value) };
                  set("discovery_feeds", updated);
                }}
                min={1}
                max={1440}
                style={inputStyle}
                placeholder={dc.discoveryFeedInterval}
              />
              <button
                type="button"
                onClick={() => set("discovery_feeds", form.discovery_feeds.filter((_, j) => j !== i))}
                style={{ background: "none", border: "none", fontSize: 13, color: "var(--error)", cursor: "pointer" }}
              >
                {dc.discoveryRemoveFeed}
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("discovery_feeds", [...form.discovery_feeds, { url: "", name: "", poll_interval_min: 15 }])}
            style={{
              padding: "6px 14px",
              background: "none",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              color: "var(--muted)",
              cursor: "pointer",
              marginBottom: 24,
            }}
          >
            {dc.discoveryAddFeed}
          </button>

          {/* Categories */}
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.discoveryCategories}
            <Tip text={dc.tipDiscoveryCategories} />
          </h4>
          {form.discovery_categories.length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 2fr auto",
                gap: 8,
                marginBottom: 4,
                fontSize: 11,
                color: "var(--muted)",
                fontWeight: 500,
              }}
            >
              <span>{dc.discoveryCategoryName}</span>
              <span>{dc.discoveryCategoryDescription}</span>
              <span></span>
            </div>
          )}
          {form.discovery_categories.map((cat, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 8, marginBottom: 8, alignItems: "start" }}>
              <input
                value={cat.name}
                onChange={(e) => {
                  const updated = [...form.discovery_categories];
                  updated[i] = { ...cat, name: e.target.value };
                  set("discovery_categories", updated);
                }}
                placeholder={dc.discoveryCategoryNamePlaceholder}
                style={inputStyle}
              />
              <textarea
                value={cat.description}
                onChange={(e) => {
                  const updated = [...form.discovery_categories];
                  updated[i] = { ...cat, description: e.target.value };
                  set("discovery_categories", updated);
                }}
                rows={2}
                placeholder={dc.discoveryCategoryDescriptionPlaceholder}
                style={{ ...inputStyle, resize: "vertical" }}
              />
              <button
                type="button"
                onClick={() => set("discovery_categories", form.discovery_categories.filter((_, j) => j !== i))}
                style={{ background: "none", border: "none", fontSize: 13, color: "var(--error)", cursor: "pointer" }}
              >
                {dc.discoveryRemoveCategory}
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("discovery_categories", [...form.discovery_categories, { name: "", description: "" }])}
            style={{
              padding: "6px 14px",
              background: "none",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              color: "var(--muted)",
              cursor: "pointer",
              marginBottom: 24,
            }}
          >
            {dc.discoveryAddCategory}
          </button>

          {/* Models */}
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
            {dc.sectionModels}
            <Tip text={dc.tipDiscoveryAgentModels} />
          </h4>
          {([
            ["discovery_classifier_model", "discovery_classifier_fallback_models", dc.discoveryClassifierModel],
            ["discovery_matcher_model", "discovery_matcher_fallback_models", dc.discoveryMatcherModel],
            ["discovery_topic_writer_model", "discovery_topic_writer_fallback_models", dc.discoveryTopicWriterModel],
          ] as const).map(([modelKey, fallbackKey, label]) => (
            <div key={modelKey} style={{ display: "grid", gridTemplateColumns: "200px 1fr 1fr", gap: 8, alignItems: "center", marginBottom: 8 }}>
              <label style={{ ...labelStyle, marginBottom: 0 }}>{label}</label>
              <select
                value={form[modelKey] as string}
                onChange={(e) => set(modelKey, e.target.value as DomainConfigData[typeof modelKey])}
                style={inputStyle}
              >
                {AVAILABLE_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
              <div style={{ position: "relative" }}>
                <input
                  value={(form[fallbackKey] as string[]).join(", ")}
                  onChange={(e) => {
                    const vals = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                    set(fallbackKey, vals as DomainConfigData[typeof fallbackKey]);
                  }}
                  placeholder={dc.discoveryFallbacks}
                  style={{ ...inputStyle, fontSize: 12, fontFamily: "monospace" }}
                />
                <span style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)" }}>
                  <Tip text={dc.tipDiscoveryFallbacks} />
                </span>
              </div>
            </div>
          ))}
        </section>
      </div>

      {/* Sticky save bar */}
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: "var(--sidebar-width)",
          right: 0,
          background: "var(--white)",
          borderTop: "1px solid var(--border)",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <button
          type="button"
          onClick={() => onSave(form)}
          disabled={saving}
          style={{
            padding: "8px 20px",
            background: saving ? "var(--border)" : "var(--accent)",
            color: saving ? "var(--muted)" : "var(--white)",
            border: "none",
            borderRadius: "var(--radius)",
            fontSize: 13,
            fontWeight: 500,
            cursor: saving ? "default" : "pointer",
          }}
        >
          {saving ? dc.saving : dc.save}
        </button>
        {error && <span style={{ fontSize: 12, color: "var(--error)" }}>{error}</span>}
        {!error && !saving && <span style={{ fontSize: 12, color: "var(--muted)" }}>{dc.saveHint}</span>}
      </div>
    </div>
  );
}
