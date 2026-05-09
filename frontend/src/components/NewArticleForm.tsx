// frontend/src/components/NewArticleForm.tsx
import { useEffect, useState } from "react";
import { useArticles } from "../lib/useArticles";
import { useApi } from "../lib/useApi";
import { useAuth } from "../lib/useAuth";
import { useT } from "../i18n";
import { useFocusTrap } from "../lib/useFocusTrap";
import { AVAILABLE_MODELS } from "./DomainConfigForm";
import { Button } from "./ui/Button";
import type { ArticleTemplate, DomainConfigData, EditorExtraction } from "../types";

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
  const { request } = useApi();
  const { user } = useAuth();
  const t = useT();
  const na = t.newArticle;

  const [mode, setMode] = useState<"basic" | "settings">("basic");
  const [activeTab, setActiveTab] = useState<TabId>("topic");
  const [step, setStep] = useState<"step1" | "step2">("step1");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [instructions, setInstructions] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [rawFacts, setRawFacts] = useState("");
  const [orgTemplates, setOrgTemplates] = useState<ArticleTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [adHocTemplate, setAdHocTemplate] = useState("");
  const [extraction, setExtraction] = useState<EditorExtraction | null>(null);
  const [skipWebResearch, setSkipWebResearch] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [instagramUrl, setInstagramUrl] = useState("");
  const [showInstagramInput, setShowInstagramInput] = useState(false);
  const [xUrl, setXUrl] = useState("");
  const [showXInput, setShowXInput] = useState(false);
  const [socialMediaAttachments, setSocialMediaAttachments] = useState<
    { platform: string; post_url: string; media_url: string; media_type: string }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function pickImage(file: File | null) {
    if (!file) { setImageFile(null); setImagePreview(null); return; }
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(typeof e.target?.result === "string" ? e.target.result : null);
    reader.readAsDataURL(file);
  }

  function pickVideo(file: File | null) {
    setVideoFile(file);
  }

  // Fetch org templates so the editor can pick one. 404 (org not configured) is silently ignored.
  useEffect(() => {
    let cancelled = false;
    void request<DomainConfigData>("/v2/domain-config")
      .then((d) => { if (!cancelled && d?.article_templates) setOrgTemplates(d.article_templates); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [request]);

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

  // Step 1 → step 2 transition. Calls the backend extract endpoint and shows
  // the editable list. Skipped when raw facts are empty (pipeline submit goes
  // straight from step 1).
  async function goToStep2() {
    if (!rawFacts.trim() && !imageFile && !videoFile && !instagramUrl.trim() && !xUrl.trim()) return;
    setExtracting(true);
    setError(null);
    try {
      const selectedTemplate = orgTemplates.find((tmpl) => tmpl.id === selectedTemplateId);
      type FetchResult = EditorExtraction & { media_url?: string; media_type?: string };
      const fetchTasks: Promise<FetchResult>[] = [];

      if (rawFacts.trim() || imageFile || videoFile) {
        const fd = new FormData();
        fd.append("topic", topic.trim());
        if (rawFacts.trim()) fd.append("raw_facts_text", rawFacts.trim());
        if (imageFile) fd.append("image", imageFile);
        if (videoFile) fd.append("video", videoFile);
        if ((imageFile || videoFile) && selectedTemplate?.image_instructions) {
          fd.append("image_instructions", selectedTemplate.image_instructions);
        }
        fetchTasks.push(request<FetchResult>("/v2/extract_editor_facts", { method: "POST", body: fd }));
      }

      // Track which task index corresponds to which social media source
      const instagramTaskIdx = instagramUrl.trim() ? fetchTasks.length : -1;
      if (instagramUrl.trim()) {
        fetchTasks.push(request<EditorExtraction & { media_url?: string; media_type?: string }>("/v2/fetch_instagram_facts", {
          method: "POST",
          body: JSON.stringify({
            url: instagramUrl.trim(),
            topic: topic.trim(),
            image_instructions: selectedTemplate?.image_instructions || null,
          }),
        }));
      }

      const xTaskIdx = xUrl.trim() ? fetchTasks.length : -1;
      if (xUrl.trim()) {
        fetchTasks.push(request<EditorExtraction & { media_url?: string; media_type?: string }>("/v2/fetch_x_facts", {
          method: "POST",
          body: JSON.stringify({ url: xUrl.trim(), topic: topic.trim() }),
        }));
      }

      const settled = await Promise.allSettled(fetchTasks);
      const allFacts: EditorExtraction["facts"] = [];
      const allQuotes: EditorExtraction["quotes"] = [];
      const allKeywordsRaw: string[] = [];
      const failedSources: string[] = [];
      const newAttachments: { platform: string; post_url: string; media_url: string; media_type: string }[] = [];
      for (let i = 0; i < settled.length; i++) {
        const result = settled[i];
        if (result.status === "fulfilled") {
          allFacts.push(...result.value.facts.map((f) => ({ text: f.text, context: f.context, source: f.source || "editor-provided" })));
          allQuotes.push(...result.value.quotes.map((q) => ({ text: q.text, speaker: q.speaker, context: q.context, source: q.source || "editor-provided" })));
          allKeywordsRaw.push(...(result.value.keywords ?? []));
          if (i === instagramTaskIdx && result.value.media_url) {
            newAttachments.push({ platform: "instagram", post_url: instagramUrl.trim(), media_url: result.value.media_url, media_type: result.value.media_type || "image/jpeg" });
          }
          if (i === xTaskIdx && result.value.media_url) {
            newAttachments.push({ platform: "x", post_url: xUrl.trim(), media_url: result.value.media_url, media_type: result.value.media_type || "" });
          }
        } else {
          if (i === instagramTaskIdx) failedSources.push("Instagram");
          if (i === xTaskIdx) failedSources.push("X.com");
        }
      }
      setSocialMediaAttachments(newAttachments);
      const allKeywords = [...new Set(allKeywordsRaw)];

      setExtraction({ facts: allFacts, quotes: allQuotes, keywords: allKeywords });
      if (failedSources.length > 0) setError(`${failedSources.join(", ")}: nie udało się pobrać posta. Wyciągnięto fakty z pozostałych źródeł.`);
      setStep("step2");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setExtracting(false);
    }
  }

  function buildAgentOverrides(): Record<string, Record<string, unknown>> {
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
    return agents;
  }

  async function submitToPipeline() {
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const urls = urlsText.split("\n").map((u) => u.trim()).filter(Boolean);
      const agents = buildAgentOverrides();
      const author_name =
        [user?.givenName, user?.familyName].filter(Boolean).join(" ") || user?.email || undefined;
      const resolvedTemplate = selectedTemplateId
        ? (orgTemplates.find((tmpl) => tmpl.id === selectedTemplateId)?.body ?? "")
        : adHocTemplate;

      // When step 2 is in play, send the (possibly edited) extraction directly
      // and the pipeline skips its in-pipeline text_extraction stage. Otherwise
      // fall back to raw_facts_text (legacy single-step path).
      const useStep2 = step === "step2" && extraction !== null;
      const result = await submitArticle({
        topic: topic.trim(),
        additional_instructions: instructions.trim() || undefined,
        urls: urls.length > 0 ? urls : undefined,
        agents: Object.keys(agents).length > 0 ? agents : undefined,
        domain_overrides: Object.keys(ov).length > 0 ? ov : undefined,
        author_name,
        article_template: resolvedTemplate.trim() || undefined,
        raw_facts_text: useStep2 ? undefined : (rawFacts.trim() || undefined),
        editor_extraction: useStep2 && extraction
          ? {
              facts: extraction.facts
                .filter((f) => f.text.trim())
                .map((f) => ({ text: f.text, context: f.context, source: f.source })),
              quotes: extraction.quotes
                .filter((q) => q.text.trim())
                .map((q) => ({ text: q.text, speaker: q.speaker, context: q.context, source: q.source })),
              keywords: extraction.keywords,
            }
          : undefined,
        skip_web_research: useStep2 ? skipWebResearch : undefined,
        social_media_attachments: socialMediaAttachments.length > 0 ? socialMediaAttachments : undefined,
      });
      setLoading(false);
      onCreated(result.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    // Step 1 → Step 2 transition fires when ANY editor input is present:
    // raw facts text, an uploaded image, or both. Step 2 always submits to
    // the pipeline.
    if (step === "step1" && (rawFacts.trim() || imageFile || videoFile || instagramUrl.trim() || xUrl.trim())) {
      await goToStep2();
    } else {
      await submitToPipeline();
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
      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          style={{
            background: "none",
            border: "none",
            color: "var(--muted)",
            fontSize: 12,
            cursor: "pointer",
            padding: "2px 0",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--muted)"; }}
        >
          {advancedOpen ? na.advancedToggleHide : na.advancedToggleShow}
        </button>
      </div>
      {advancedOpen && (
        <>
      <div style={{ marginTop: 14 }}>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.templateLabel}</label>
        {orgTemplates.length > 0 && (
          <select
            value={selectedTemplateId}
            onChange={(e) => { setSelectedTemplateId(e.target.value); setAdHocTemplate(""); }}
            disabled={loading}
            style={{ ...inputStyle, marginBottom: 6 }}
          >
            <option value="">{na.templateNone}</option>
            {orgTemplates.map((tmpl) => (
              <option key={tmpl.id} value={tmpl.id}>{tmpl.name || tmpl.id}</option>
            ))}
          </select>
        )}
        {selectedTemplateId ? (
          <div style={{
            padding: "8px 10px",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            fontSize: 12,
            color: "var(--muted)",
            fontFamily: "monospace",
            maxHeight: 120,
            overflowY: "auto",
            background: "var(--accent-lt)",
            whiteSpace: "pre-wrap",
          }}>
            {orgTemplates.find((tmpl) => tmpl.id === selectedTemplateId)?.body}
          </div>
        ) : (
          <textarea
            value={adHocTemplate}
            onChange={(e) => setAdHocTemplate(e.target.value)}
            disabled={loading}
            placeholder={na.templateAdHocPlaceholder}
            rows={3}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        )}
      </div>
      <div style={{ marginTop: 14 }}>
        <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{na.factsLabel}</label>
        <textarea
          value={rawFacts}
          onChange={(e) => setRawFacts(e.target.value)}
          disabled={loading}
          placeholder={na.factsPlaceholder}
          rows={4}
          style={{ ...inputStyle, resize: "vertical" }}
        />
        {/* Image preview */}
        {imagePreview && (
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: 8, marginTop: 8, border: "1px solid var(--border)", borderRadius: "var(--radius)" }}>
            <img src={imagePreview} alt="preview" style={{ width: 72, height: 72, objectFit: "cover", borderRadius: "var(--radius)", flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{imageFile?.name}</div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>{imageFile ? `${Math.round(imageFile.size / 1024)} KB` : ""}</div>
              <button type="button" onClick={() => pickImage(null)} disabled={loading || extracting}
                style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", padding: 0 }}>
                {na.removeImage}
              </button>
            </div>
          </div>
        )}
        {/* Video preview */}
        {videoFile && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: 8, marginTop: 8, border: "1px solid var(--border)", borderRadius: "var(--radius)" }}>
            <span style={{ fontSize: 24, flexShrink: 0 }}>🎬</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{videoFile.name}</div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>{`${Math.round(videoFile.size / 1024)} KB`}</div>
              <button type="button" onClick={() => pickVideo(null)} disabled={loading || extracting}
                style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", padding: 0 }}>
                {na.removeVideo}
              </button>
            </div>
          </div>
        )}
        {/* X.com URL input */}
        {showXInput && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, padding: "6px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}>
            <span style={{ fontSize: 14, flexShrink: 0, fontWeight: 700 }}>𝕏</span>
            <input
              autoFocus
              value={xUrl}
              onChange={(e) => setXUrl(e.target.value)}
              placeholder={na.xUrlPlaceholder}
              disabled={loading || extracting}
              style={{ ...inputStyle, flex: 1, fontSize: 12, fontFamily: "monospace" }}
            />
            <button type="button" onClick={() => { setXUrl(""); setShowXInput(false); }} disabled={loading || extracting}
              style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", padding: 0, flexShrink: 0 }}>
              {na.removeX}
            </button>
          </div>
        )}
        {/* Instagram URL input */}
        {showInstagramInput && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, padding: "6px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>📸</span>
            <input
              autoFocus
              value={instagramUrl}
              onChange={(e) => setInstagramUrl(e.target.value)}
              placeholder={na.instagramUrlPlaceholder}
              disabled={loading || extracting}
              style={{ ...inputStyle, flex: 1, fontSize: 12, fontFamily: "monospace" }}
            />
            <button type="button" onClick={() => { setInstagramUrl(""); setShowInstagramInput(false); }} disabled={loading || extracting}
              style={{ background: "none", border: "none", fontSize: 12, color: "var(--error)", cursor: "pointer", padding: 0, flexShrink: 0 }}>
              {na.removeInstagram}
            </button>
          </div>
        )}
        {/* Add image / add video / add instagram buttons */}
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          {!imagePreview && !videoFile && (
            <>
              <label htmlFor="newArticleImage" style={{ display: "inline-block", padding: "5px 12px", background: "none", border: "1px dashed var(--border)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--muted)", cursor: (loading || extracting) ? "default" : "pointer" }}>
                {na.addImage}
              </label>
              <input id="newArticleImage" type="file" accept="image/*" disabled={loading || extracting} style={{ display: "none" }} onChange={(e) => pickImage(e.target.files?.[0] ?? null)} />
              <label htmlFor="newArticleVideo" style={{ display: "inline-block", padding: "5px 12px", background: "none", border: "1px dashed var(--border)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--muted)", cursor: (loading || extracting) ? "default" : "pointer" }}>
                {na.addVideo}
              </label>
              <input id="newArticleVideo" type="file" accept="video/*" disabled={loading || extracting} style={{ display: "none" }} onChange={(e) => pickVideo(e.target.files?.[0] ?? null)} />
            </>
          )}
          {!showInstagramInput && (
            <button type="button" onClick={() => setShowInstagramInput(true)} disabled={loading || extracting}
              style={{ display: "inline-block", padding: "5px 12px", background: "none", border: "1px dashed var(--border)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--muted)", cursor: (loading || extracting) ? "default" : "pointer" }}>
              {na.addInstagram}
            </button>
          )}
          {!showXInput && (
            <button type="button" onClick={() => setShowXInput(true)} disabled={loading || extracting}
              style={{ display: "inline-block", padding: "5px 12px", background: "none", border: "1px dashed var(--border)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--muted)", cursor: (loading || extracting) ? "default" : "pointer" }}>
              {na.addX}
            </button>
          )}
        </div>
        <p style={{ fontSize: 11, color: "var(--muted)", margin: "6px 0 0" }}>{na.mediaHint}</p>
      </div>
        </>
      )}
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
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
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
            {step === "step2" ? na.step2Heading : (isSettings ? na.headingSettings : na.heading)}
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
          {step === "step2" ? (
            // ── Step 2: review / edit extracted facts and quotes ─────────
            <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
              <p style={{ fontSize: 13, color: "var(--muted)", margin: "0 0 16px" }}>
                {na.step2Hint}
              </p>

              {/* Facts list */}
              <h4 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 8px", color: "var(--text)" }}>
                {na.step2FactsLabel} ({extraction?.facts.length ?? 0})
              </h4>
              {extraction && extraction.facts.length === 0 && (
                <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px" }}>{na.step2NoFacts}</p>
              )}
              {extraction?.facts.map((f, i) => {
                const fromPhoto = f.source === "editor-provided-photo";
                const fromVideo = f.source === "editor-provided-video";
                const fromInstagram = f.source === "editor-provided-instagram";
                const fromX = f.source === "editor-provided-x";
                return (
                <div key={`f-${i}`} style={{ marginBottom: 10, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)", background: (fromPhoto || fromVideo || fromInstagram || fromX) ? "var(--accent-lt)" : undefined }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: "var(--muted)", display: "inline-flex", alignItems: "center", gap: 4 }}>
                      {fromPhoto && <span title="ze zdjęcia">📷</span>}
                      {fromVideo && <span title="z wideo">🎬</span>}
                      {fromInstagram && <span title="z Instagrama">📸</span>}
                      {fromX && <span title="z X.com">𝕏</span>}
                      {na.step2FactText} {i + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => setExtraction((prev) => prev ? { ...prev, facts: prev.facts.filter((_, j) => j !== i) } : prev)}
                      style={{ background: "none", border: "none", fontSize: 11, color: "var(--error)", cursor: "pointer" }}
                    >
                      {na.step2RemoveFact}
                    </button>
                  </div>
                  <textarea
                    value={f.text}
                    onChange={(e) => setExtraction((prev) => {
                      if (!prev) return prev;
                      const facts = [...prev.facts];
                      facts[i] = { ...facts[i], text: e.target.value };
                      return { ...prev, facts };
                    })}
                    rows={2}
                    style={{ ...inputStyle, resize: "vertical", marginBottom: 4 }}
                  />
                  <input
                    value={f.context}
                    onChange={(e) => setExtraction((prev) => {
                      if (!prev) return prev;
                      const facts = [...prev.facts];
                      facts[i] = { ...facts[i], context: e.target.value };
                      return { ...prev, facts };
                    })}
                    placeholder={na.step2FactContext}
                    style={{ ...inputStyle, fontSize: 12 }}
                  />
                </div>
                );
              })}
              <button
                type="button"
                onClick={() => setExtraction((prev) => prev ? { ...prev, facts: [...prev.facts, { text: "", context: "", source: "editor-provided" }] } : prev)}
                style={{ padding: "4px 10px", background: "none", border: "1px dashed var(--border)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--muted)", cursor: "pointer", marginBottom: 20 }}
              >
                {na.step2AddFact}
              </button>

              {/* Quotes list */}
              <h4 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 8px", color: "var(--text)" }}>
                {na.step2QuotesLabel} ({extraction?.quotes.length ?? 0})
              </h4>
              {extraction && extraction.quotes.length === 0 && (
                <p style={{ fontSize: 12, color: "var(--muted)", margin: "0 0 10px" }}>{na.step2NoQuotes}</p>
              )}
              {extraction?.quotes.map((q, i) => {
                const fromPhoto = q.source === "editor-provided-photo";
                const fromVideo = q.source === "editor-provided-video";
                const fromInstagram = q.source === "editor-provided-instagram";
                const fromX = q.source === "editor-provided-x";
                return (
                <div key={`q-${i}`} style={{ marginBottom: 10, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)", background: (fromPhoto || fromVideo || fromInstagram || fromX) ? "var(--accent-lt)" : undefined }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: "var(--muted)", display: "inline-flex", alignItems: "center", gap: 4 }}>
                      {fromPhoto && <span title="ze zdjęcia">📷</span>}
                      {fromVideo && <span title="z wideo">🎬</span>}
                      {fromInstagram && <span title="z Instagrama">📸</span>}
                      {fromX && <span title="z X.com">𝕏</span>}
                      {na.step2QuoteText} {i + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => setExtraction((prev) => prev ? { ...prev, quotes: prev.quotes.filter((_, j) => j !== i) } : prev)}
                      style={{ background: "none", border: "none", fontSize: 11, color: "var(--error)", cursor: "pointer" }}
                    >
                      {na.step2RemoveQuote}
                    </button>
                  </div>
                  <textarea
                    value={q.text}
                    onChange={(e) => setExtraction((prev) => {
                      if (!prev) return prev;
                      const quotes = [...prev.quotes];
                      quotes[i] = { ...quotes[i], text: e.target.value };
                      return { ...prev, quotes };
                    })}
                    rows={2}
                    style={{ ...inputStyle, resize: "vertical", marginBottom: 4 }}
                  />
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 4 }}>
                    <input
                      value={q.speaker}
                      onChange={(e) => setExtraction((prev) => {
                        if (!prev) return prev;
                        const quotes = [...prev.quotes];
                        quotes[i] = { ...quotes[i], speaker: e.target.value };
                        return { ...prev, quotes };
                      })}
                      placeholder={na.step2QuoteSpeaker}
                      style={{ ...inputStyle, fontSize: 12 }}
                    />
                    <input
                      value={q.context}
                      onChange={(e) => setExtraction((prev) => {
                        if (!prev) return prev;
                        const quotes = [...prev.quotes];
                        quotes[i] = { ...quotes[i], context: e.target.value };
                        return { ...prev, quotes };
                      })}
                      placeholder={na.step2QuoteContext}
                      style={{ ...inputStyle, fontSize: 12 }}
                    />
                  </div>
                </div>
                );
              })}
              <button
                type="button"
                onClick={() => setExtraction((prev) => prev ? { ...prev, quotes: [...prev.quotes, { text: "", speaker: "", context: "", source: "editor-provided" }] } : prev)}
                style={{ padding: "4px 10px", background: "none", border: "1px dashed var(--border)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--muted)", cursor: "pointer", marginBottom: 20 }}
              >
                {na.step2AddQuote}
              </button>

              {/* Web search toggle */}
              <div style={{ marginTop: 8, padding: "10px 12px", background: "var(--accent-lt)", borderRadius: "var(--radius)" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={!skipWebResearch}
                    onChange={(e) => setSkipWebResearch(!e.target.checked)}
                    style={{ accentColor: "var(--accent)" }}
                  />
                  <span style={{ fontWeight: 500 }}>{na.step2WebSearchLabel}</span>
                </label>
                <p style={{ fontSize: 11, color: "var(--muted)", margin: "4px 0 0 24px" }}>
                  {na.step2WebSearchHint}
                </p>
              </div>
            </div>
          ) : isSettings ? (
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
            {step === "step2" ? (
              <button
                type="button"
                onClick={() => { setStep("step1"); setError(null); }}
                disabled={loading}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--muted)",
                  fontSize: 13,
                  cursor: loading ? "default" : "pointer",
                  padding: "4px 0",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "var(--accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "var(--muted)"; }}
              >
                {na.back}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setMode(isSettings ? "basic" : "settings")}
                disabled={loading || extracting}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--muted)",
                  fontSize: 13,
                  cursor: (loading || extracting) ? "default" : "pointer",
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
            )}
            <div style={{ display: "flex", gap: 8 }}>
              {onCancel && (
                <Button variant="ghost" size="md" onClick={onCancel} disabled={loading || extracting} type="button">
                  {na.cancel}
                </Button>
              )}
              {step === "step2" ? (
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={loading || !topic.trim()}
                >
                  {loading ? na.generating : na.generateArticle}
                </Button>
              ) : (rawFacts.trim() || imageFile || videoFile || instagramUrl.trim() || xUrl.trim()) ? (
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={loading || extracting || !topic.trim()}
                >
                  {extracting ? (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: 12,
                          height: 12,
                          border: "2px solid currentColor",
                          borderTopColor: "transparent",
                          borderRadius: "50%",
                          animation: "spin 0.8s linear infinite",
                        }}
                      />
                      {na.step2Extracting}
                    </span>
                  ) : (
                    na.next
                  )}
                </Button>
              ) : (
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={loading || !topic.trim()}
                >
                  {loading ? na.generating : na.generate}
                </Button>
              )}
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
