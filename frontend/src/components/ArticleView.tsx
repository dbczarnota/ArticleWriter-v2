import { useEffect, useState, useCallback } from "react";
import DOMPurify from "dompurify";
import type { Article, EmbedCandidate, Fact, Quote, SocialMediaAttachment } from "../types";
import { useArticles } from "../lib/useArticles";
import { useMediaQuery } from "../lib/useMediaQuery";
import { useLang, useT } from "../i18n";
import { CollapsibleSection } from "./CollapsibleSection";
import { Button } from "./ui/Button";
import { CodeIcon, CopyIcon, DownloadIcon } from "./ui/icons";
import { safeHref } from "../lib/safeHref";
import { useApi } from "../lib/useApi";

interface ArticleViewProps {
  articleId: string;
  currentUserId?: string;
  onMarkDone?: (id: string, done: boolean) => Promise<void>;
}

export function ArticleView({ articleId, currentUserId, onMarkDone }: ArticleViewProps) {
  const { fetchArticle } = useArticles();
  const t = useT();
  const av = t.articleView;
  const { lang } = useLang();
  const isMobile = useMediaQuery("(max-width: 767px)");
  const [article, setArticle] = useState<Article | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setArticle(null);
    setError(null);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function load() {
      try {
        const a = await fetchArticle(articleId);
        if (cancelled) return;
        setArticle(a);
        if (a.status === "running") {
          timer = setTimeout(load, 4000);
        }
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [articleId]);

  if (error) return <p style={{ color: "var(--error)" }}>{av.error}: {error}</p>;
  if (!article) return <p style={{ color: "var(--muted)" }}>{av.loading}</p>;

  const STAGE_LABELS: Record<string, string> = {
    search: av.stageSearch,
    scraping: av.stageScraping,
    parsing: av.stageParsing,
    extraction: av.stageExtraction,
    adaptive_search: av.stageAdaptive,
    media_search: av.stageMedia,
    instructions: av.stageInstructions,
    writer: av.stageWriter,
    reflection: av.stageReflection,
    followup: av.stageFollowup,
  };
  // Adaptive_search loop sets fine-grained sub-stages like
  // 'adaptive_search.r2.scraping'. Map the trailing substep to a label so the
  // user sees what the pipeline is actually waiting on. Round number is
  // intentionally hidden — exposing 'r2' would invite questions about a
  // budget that's purely an implementation detail.
  const ADAPTIVE_SUBSTAGE_LABELS: Record<string, string> = {
    decide: av.stageAdaptiveDecide,
    serper: av.stageAdaptiveSerper,
    scraping: av.stageAdaptiveScraping,
    parsing: av.stageAdaptiveParsing,
    extraction: av.stageAdaptiveExtraction,
  };
  function resolveStageLabel(stage: string | null): string {
    if (!stage) return av.stageDefault;
    if (stage in STAGE_LABELS) return STAGE_LABELS[stage];
    if (stage.startsWith("adaptive_search.")) {
      const substep = stage.split(".").pop() ?? "";
      return ADAPTIVE_SUBSTAGE_LABELS[substep] ?? av.stageAdaptive;
    }
    return stage;  // surface raw label rather than crash if backend introduces a new stage
  }

  // Same fallback chain as the done-view title bar — author_name (Kinde
  // full name) → email handle → 'Inny redaktor'. Surfaced via a helper so
  // both views share the logic instead of forking it.
  function resolveAuthorLabel(): string {
    const isMe = !!currentUserId && article!.author_user_id === currentUserId;
    if (article!.author_name) {
      return isMe ? `${av.me} (${article!.author_name})` : article!.author_name;
    }
    if (article!.author_email) {
      const handle = article!.author_email.split("@")[0];
      return isMe ? `${av.me} (${handle})` : handle;
    }
    return isMe ? av.me : av.otherEditor;
  }

  if (article.status === "running") {
    const stageLabel = resolveStageLabel(article.pipeline_stage);
    return (
      <div>
        <div style={{ display: "flex", gap: 12, fontSize: 12, color: "var(--muted)", marginBottom: 6, flexWrap: "wrap" }}>
          <span>{resolveAuthorLabel()}</span>
          <span>{article.created_at ? new Date(article.created_at).toLocaleString(lang) : "—"}</span>
        </div>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>{article.topic}</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)", fontSize: 14 }}>
          <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          {stageLabel}
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const usedFacts = article.facts.filter((f) => f.was_used);
  const rejectedFacts = article.facts.filter((f) => !f.was_used);
  const usedQuotes = article.quotes.filter((q) => q.was_used);
  const rejectedQuotes = article.quotes.filter((q) => !q.was_used);

  // Failed article: every body-section would render empty or near-empty,
  // which buries the actually-useful information (what the editor asked
  // for). Render the inputs panel only and skip the rest.
  const isFailed = article.status === "failed" || article.status === "insufficient_sources";

  // Each fact / quote now carries `source_urls` (a list of every article
  // that asserted it). Compute used vs. unused over the union of all
  // source_urls: a URL is "used" when at least one was_used=true item
  // includes it; anything else lands in "unused".
  const allItems: Array<{ was_used: boolean; source_urls: string[] }> = [
    ...article.facts,
    ...article.quotes,
  ];
  const usedSourcesSet = new Set<string>();
  const unusedSourcesSet = new Set<string>();
  for (const item of allItems) {
    const target = item.was_used ? usedSourcesSet : unusedSourcesSet;
    for (const url of item.source_urls ?? []) {
      if (url) target.add(url);
    }
  }
  const usedSources = [...usedSourcesSet];
  const uniqueUnused = [...unusedSourcesSet].filter((url) => !usedSourcesSet.has(url));

  async function handleCopy() {
    await navigator.clipboard.writeText(article!.html ?? "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleExport() {
    const a0 = article!;
    const blob = new Blob([a0.html ?? ""], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${a0.topic.replace(/[^a-z0-9]/gi, "-").toLowerCase()}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const totalTokens = article.usage_events.reduce(
    (s, e) => s + e.input_tokens + e.output_tokens,
    0
  );

  // Strip HTML tags + collapse whitespace, then count words and characters
  // (characters include spaces, exclude HTML markup). Done client-side because
  // the source of truth is article.html and we don't want to drift if the
  // backend later edits it.
  const plainText = (article.html ?? "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const wordCount = plainText ? plainText.split(" ").length : 0;
  const charCount = plainText.length;

  return (
    <div>
      {/* Toolbar — flex row on desktop, stacked on mobile so the action
          buttons don't squeeze the title into a vertical letter column. */}
      <div style={{
        display: "flex",
        flexDirection: isMobile ? "column" : "row",
        alignItems: isMobile ? "stretch" : "flex-start",
        justifyContent: "space-between",
        marginBottom: 20,
        gap: isMobile ? 12 : 16,
      }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--muted)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            <span>{av.statWords}: <strong style={{ color: "var(--text)" }}>{wordCount.toLocaleString()}</strong></span>
            <span>{av.statChars}: <strong style={{ color: "var(--text)" }}>{charCount.toLocaleString()}</strong></span>
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 6 }}>{article.topic}</h2>
          <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--muted)", flexWrap: "wrap", alignItems: "center" }}>
            <span>
              {(() => {
                const isMe = !!currentUserId && article.author_user_id === currentUserId;
                // Prefer the explicit author_name (full name from Kinde JWT,
                // sent by the frontend on create). Fall back to the email
                // local-part for legacy rows. Last resort: 'Inny redaktor'.
                if (article.author_name) {
                  return isMe ? `${av.me} (${article.author_name})` : article.author_name;
                }
                if (article.author_email) {
                  const handle = article.author_email.split("@")[0];
                  return isMe ? `${av.me} (${handle})` : handle;
                }
                return isMe ? av.me : av.otherEditor;
              })()}
            </span>
            <span>{article.created_at ? new Date(article.created_at).toLocaleString(lang) : "—"}</span>
            <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", userSelect: "none" }}>
              <input
                type="checkbox"
                checked={article.marked_done}
                onChange={async (e) => {
                  const done = e.target.checked;
                  setArticle((a) => a ? { ...a, marked_done: done } : a);
                  try {
                    await onMarkDone?.(article.id, done);
                  } catch {
                    setArticle((a) => a ? { ...a, marked_done: !done } : a);
                  }
                }}
                style={{ width: 14, height: 14, accentColor: "var(--success)", cursor: "pointer" }}
              />
              <span style={{ fontWeight: article.marked_done ? 600 : 400, color: article.marked_done ? "var(--success)" : "var(--muted)" }}>
                {article.marked_done ? `${av.markDone} ✓` : av.markDone}
              </span>
              {article.marked_done && article.marked_done_by_name && (
                <span style={{ color: "var(--muted)", fontSize: 11 }}>
                  {av.markedBy} {article.marked_done_by_name}
                </span>
              )}
            </label>
          </div>
        </div>
        <div style={{
          display: "flex",
          gap: 8,
          flexShrink: 0,
          flexWrap: "wrap",
          // On mobile the toolbar stacks; let the action row span full width.
          width: isMobile ? "100%" : "auto",
          justifyContent: isMobile ? "flex-start" : "flex-start",
        }}>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            iconLeft={<CopyIcon />}
            style={copied ? { background: "var(--success)", color: "var(--fg-inverse)", borderColor: "var(--success)" } : undefined}
            title={av.copyHtml}
          >
            {copied ? av.copied : av.copyHtml}
          </Button>
          <Button variant="primary" size="sm" onClick={handleExport}>
            {av.exportHtml}
          </Button>
        </div>
      </div>

      {/* Failed-status banner — explains why the body is mostly empty. */}
      {isFailed && (
        <div style={{
          padding: 16,
          background: "var(--error-lt)",
          border: "1px solid var(--error)",
          borderRadius: "var(--radius)",
          marginBottom: 20,
        }}>
          <p style={{ fontSize: 14, fontWeight: 600, color: "var(--error-fg)", marginBottom: 4 }}>
            {av.failedTitle}
          </p>
          <p style={{ fontSize: 12, color: "var(--error-fg)" }}>
            {av.failedHint}
          </p>
        </div>
      )}

      {/* Article HTML */}
      {!isFailed && article.html && (
        <div
          className="article-html"
          // Article HTML comes from the LLM pipeline. Even though we control the
          // pipeline, prompt-injection from any third-party source URL could
          // smuggle <script> or onerror= payloads into the output. DOMPurify
          // strips all script/event-handler vectors while keeping the
          // formatting tags the writer actually emits (h1-h3, p, ul, ol, li,
          // blockquote, a, strong, em).
          dangerouslySetInnerHTML={{
            __html: DOMPurify.sanitize(article.html, { USE_PROFILES: { html: true } }),
          }}
          style={{
            padding: "28px 36px",
            background: "var(--card-bg)",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-card)",
            marginBottom: 24,
            lineHeight: 1.7,
          }}
        />
      )}

      {/* Alternative titles */}
      {!isFailed && article.alternative_titles.length > 0 && (
        <CollapsibleSection prominent title={av.altTitles} count={article.alternative_titles.length} defaultOpen>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {article.alternative_titles.map((title, i) => (
              <div key={i} style={{ padding: "8px 12px", background: "var(--card-bg)", border: "1px solid var(--card-border)", borderRadius: "var(--radius-lg)", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <span>{title}</span>
                <CopyButton text={title} />
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Follow-up topics */}
      {!isFailed && article.followup_topics.length > 0 && (
        <CollapsibleSection prominent title={av.followupTopics} count={article.followup_topics.length} defaultOpen>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {article.followup_topics.map((topic, i) => (
              <span key={i} style={{ padding: "5px 10px", background: "var(--accent-lt)", border: "1px solid var(--accent)", borderRadius: 20, fontSize: 12, color: "var(--accent)", fontWeight: 500 }}>
                {topic}
              </span>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Facebook teasers */}
      {!isFailed && article.facebook_teasers.length > 0 && (
        <CollapsibleSection prominent title={av.facebookTeasers} count={article.facebook_teasers.length} defaultOpen>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {article.facebook_teasers.map((teaser, i) => (
              <TeaserCard key={i} text={teaser} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Social media embeds */}
      {!isFailed && (article.social_media_attachments.length > 0 || article.embed_candidates.length > 0) && (
        <CollapsibleSection prominent title={av.socialMedia} count={article.social_media_attachments.length + article.embed_candidates.length}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {article.social_media_attachments.map((att, i) => (
              <SocialMediaAttachmentCard key={i} attachment={att} t={av} />
            ))}
            {[...article.embed_candidates].sort((a, b) => (b.competitor_source_url ? 1 : 0) - (a.competitor_source_url ? 1 : 0)).map((e) => (
              <EmbedCandidateRow key={e.id} e={e} t={av} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {!isFailed && (
        <>
          {/* Facts */}
          <CollapsibleSection prominent title={av.factsUsed} count={usedFacts.length} defaultOpen>
            {usedFacts.map((f) => (
              <FactCard key={f.id} fact={f} />
            ))}
            <CollapsibleSection title={av.factsRejected} count={rejectedFacts.length}>
              {rejectedFacts.map((f) => (
                <FactCard key={f.id} fact={f} muted />
              ))}
            </CollapsibleSection>
          </CollapsibleSection>

          {/* Quotes */}
          <CollapsibleSection prominent title={av.quotesUsed} count={usedQuotes.length} defaultOpen>
            {usedQuotes.map((q) => (
              <QuoteCard key={q.id} quote={q} />
            ))}
            <CollapsibleSection title={av.quotesRejected} count={rejectedQuotes.length}>
              {rejectedQuotes.map((q) => (
                <QuoteCard key={q.id} quote={q} muted />
              ))}
            </CollapsibleSection>
          </CollapsibleSection>

          {/* Sources */}
          <CollapsibleSection prominent title={av.sourcesUsed} count={usedSources.length} defaultOpen>
            {usedSources.map((url) => (
              <div key={url} style={{ borderLeft: "3px solid var(--success)", paddingLeft: 10, marginBottom: 6, fontSize: 13 }}>
                <a href={safeHref(url)} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", wordBreak: "break-all" }}>{url}</a>
              </div>
            ))}
            <CollapsibleSection title={av.sourcesUnused} count={uniqueUnused.length}>
              {uniqueUnused.map((url) => (
                <div key={url} style={{ borderLeft: "3px solid var(--card-border)", paddingLeft: 10, marginBottom: 6, fontSize: 13 }}>
                  <a href={safeHref(url)} target="_blank" rel="noreferrer" style={{ color: "var(--muted)", wordBreak: "break-all" }}>{url}</a>
                </div>
              ))}
            </CollapsibleSection>
          </CollapsibleSection>

          {/* Stats — words/chars are surfaced above the title so they're
              always visible; the rest stays in this collapsible block. */}
          <CollapsibleSection prominent title={av.pipelineStats}>
            <div style={{ padding: "8px 0", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, fontSize: 13 }}>
              <Stat label={av.statTime} value={article.total_duration_ms != null ? (article.total_duration_ms / 1000).toFixed(1) : "—"} />
              <Stat label={av.statFacts} value={article.facts.length} />
              <Stat label={av.statQuotes} value={article.quotes.length} />
              <Stat label={av.statEmbeds} value={article.embed_candidates.length} />
              <Stat label={av.statAgentCalls} value={article.usage_events.length} />
              <Stat label={av.statTokens} value={totalTokens.toLocaleString()} />
            </div>
            {/* Article ID — copyable so it can be pasted directly into a
                Logfire `WHERE article_id = '...'` query. Monospace + small. */}
            <div style={{
              marginTop: 12,
              paddingTop: 10,
              borderTop: "1px solid var(--card-border)",
              fontSize: 11,
              color: "var(--muted)",
              display: "flex",
              gap: 6,
              flexWrap: "wrap",
              alignItems: "baseline",
            }}>
              <span>{av.statArticleId}:</span>
              <code style={{ fontFamily: "ui-monospace, monospace", color: "var(--text)", wordBreak: "break-all" }}>
                {article.id}
              </code>
            </div>
          </CollapsibleSection>
        </>
      )}

      {/* Inputs — always visible. For successful articles it sits at the
          bottom for reference; for failed ones it's the only body section,
          so an editor can copy what they typed and try again. */}
      <CollapsibleSection prominent title={av.inputs} defaultOpen={isFailed}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "8px 0" }}>
          <InputRow label={av.inputTopic} value={article.topic} />
          <InputRow
            label={av.inputInstructions}
            value={article.additional_instructions || av.inputNone}
            preserveWhitespace
          />
          <div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginBottom: 4 }}>{av.inputUrls}</div>
            {article.input_urls.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--muted)" }}>{av.inputNone}</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {article.input_urls.map((u) => (
                  <a key={u} href={safeHref(u)} target="_blank" rel="noreferrer" style={{ fontSize: 13, color: "var(--accent)", wordBreak: "break-all" }}>{u}</a>
                ))}
              </div>
            )}
          </div>
        </div>
      </CollapsibleSection>
    </div>
  );
}

function CorroborationBadge({ count }: { count: number }) {
  if (count <= 1) return null;
  return (
    <span style={{
      display: "inline-block",
      fontSize: 10,
      fontWeight: 700,
      color: "var(--success-fg)",
      background: "var(--success-lt)",
      border: "1px solid #86efac",
      borderRadius: 10,
      padding: "1px 6px",
      marginLeft: 6,
    }} title={`Potwierdzone w ${count} źródłach`}>
      ×{count}
    </span>
  );
}

function SourceList({ urls }: { urls: string[] }) {
  if (!urls || urls.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 4 }}>
      {urls.map((u) => (
        <a key={u} href={safeHref(u)} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "var(--accent)", wordBreak: "break-all" }}>
          {u}
        </a>
      ))}
    </div>
  );
}

function FactCard({ fact, muted }: { fact: Fact; muted?: boolean }) {
  const corroboration = fact.source_urls?.length ?? 0;
  return (
    <div style={{
      borderLeft: `3px solid ${muted ? "var(--card-border)" : "var(--accent)"}`,
      marginBottom: 8,
      background: muted ? "transparent" : "var(--accent-lt)",
      borderRadius: "0 var(--radius-lg) var(--radius-lg) 0",
      padding: "8px 8px 8px 12px",
    }}>
      <p style={{ fontSize: 13, marginBottom: 4 }}>
        {fact.text}
        <CorroborationBadge count={corroboration} />
      </p>
      {fact.context && <p style={{ fontSize: 12, color: "var(--muted)" }}>{fact.context}</p>}
      <SourceList urls={fact.source_urls ?? []} />
    </div>
  );
}

function QuoteCard({ quote, muted }: { quote: Quote; muted?: boolean }) {
  const corroboration = quote.source_urls?.length ?? 0;
  return (
    <div style={{
      borderLeft: `3px solid ${muted ? "var(--card-border)" : "var(--accent)"}`,
      padding: "8px 8px 8px 12px",
      marginBottom: 8,
      background: muted ? "transparent" : "var(--accent-lt)",
      borderRadius: "0 var(--radius-lg) var(--radius-lg) 0",
    }}>
      <p style={{ fontSize: 13, fontStyle: "italic" }}>
        "{quote.text}"
        <CorroborationBadge count={corroboration} />
      </p>
      {quote.speaker && <p style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>— {quote.speaker}</p>}
      {quote.context && <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{quote.context}</p>}
      <SourceList urls={quote.source_urls ?? []} />
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function handleClick() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={handleClick}
      title="Kopiuj do schowka"
      style={{ padding: "3px 4px", background: "transparent", color: copied ? "var(--success)" : "var(--muted)", border: "none", cursor: "pointer", lineHeight: 1, borderRadius: "var(--radius)", flexShrink: 0 }}
    >
      {copied ? (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <CopyIcon />
      )}
    </button>
  );
}

function TeaserCard({ text }: { text: string }) {
  return (
    <div style={{ position: "relative", padding: "10px 44px 10px 12px", background: "var(--card-bg)", border: "1px solid var(--card-border)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-card)", fontSize: 13, minHeight: 48, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {text}
      <div style={{ position: "absolute", top: 6, right: 6 }}>
        <CopyButton text={text} />
      </div>
    </div>
  );
}

function buildEmbedCode(url: string, source: string): string {
  if (source === "instagram") {
    return `<blockquote class="instagram-media" data-instgrm-permalink="${url}" data-instgrm-version="14"><a href="${url}"></a></blockquote>\n<script async src="//www.instagram.com/embed.js"></script>`;
  }
  return `<blockquote class="twitter-tweet"><a href="${url}"></a></blockquote>\n<script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>`;
}

function EmbedCandidateRow({ e, t }: { e: EmbedCandidate; t: ReturnType<typeof useT>["articleView"] }) {
  const { downloadFile } = useApi();
  const [downloading, setDownloading] = useState(false);
  const [embedCopied, setEmbedCopied] = useState(false);
  const isApify = e.source === "instagram" || e.source === "twitter";

  const handleDownload = useCallback(async () => {
    setDownloading(true);
    try {
      await downloadFile(`/v2/download_social_post?url=${encodeURIComponent(e.url)}`, `${e.source}_media`);
    } finally {
      setDownloading(false);
    }
  }, [e.url, e.source, downloadFile]);

  const handleCopyEmbed = useCallback(() => {
    navigator.clipboard.writeText(buildEmbedCode(e.url, e.source)).then(() => {
      setEmbedCopied(true);
      setTimeout(() => setEmbedCopied(false), 2000);
    });
  }, [e.url, e.source]);

  return (
    <div style={{ display: "flex", gap: 10, padding: "8px 12px", background: e.competitor_source_url ? "var(--warning-lt)" : "var(--card-bg)", border: `1px solid ${e.competitor_source_url ? "var(--warning)" : "var(--card-border)"}`, borderRadius: "var(--radius)", fontSize: 13, alignItems: "flex-start" }}>
      {e.thumbnail_url && <img src={e.thumbnail_url} alt="" onError={(ev) => { (ev.target as HTMLImageElement).style.display = "none"; }} style={{ width: 64, height: 48, objectFit: "cover", borderRadius: 4, flexShrink: 0 }} />}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 2, flexWrap: "wrap" }}>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", color: "var(--muted)" }}>{e.source}</span>
          {e.channel && <span style={{ fontSize: 11, color: "var(--muted)" }}>· {e.channel}</span>}
          {e.competitor_source_url && (
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", color: "var(--warning-fg)", background: "var(--warning-lt)", padding: "1px 5px", borderRadius: 3, letterSpacing: "0.04em" }}>
              {t.competitorStar}
            </span>
          )}
        </div>
        <a href={safeHref(e.url)} target="_blank" rel="noreferrer" style={{ fontWeight: 500, color: "var(--accent)", wordBreak: "break-word" }}>
          {e.title ?? e.url}
        </a>
        {e.description && <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 2, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{e.description}</p>}
        {e.competitor_source_url && (
          <p style={{ fontSize: 11, color: "var(--warning-fg)", marginTop: 4 }}>
            {t.sourceLabel} <a href={safeHref(e.competitor_source_url)} target="_blank" rel="noreferrer" style={{ color: "var(--warning-fg)", textDecoration: "underline", wordBreak: "break-all" }}>{e.competitor_source_url}</a>
          </p>
        )}
      </div>
      {isApify && (
        <div style={{ display: "flex", flexDirection: "column", gap: 2, flexShrink: 0 }}>
          <button
            onClick={handleCopyEmbed}
            title="Kopiuj kod embed"
            style={{ padding: "3px 4px", background: "transparent", color: embedCopied ? "var(--success)" : "var(--muted)", border: "none", cursor: "pointer", lineHeight: 1, borderRadius: "var(--radius)", opacity: embedCopied ? 1 : 0.55 }}
          >
            {embedCopied ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <CodeIcon />
            )}
          </button>
          <button
            onClick={handleDownload}
            disabled={downloading}
            title="Pobierz media z posta"
            style={{ padding: "3px 4px", background: "transparent", color: "var(--muted)", border: "none", cursor: downloading ? "default" : "pointer", lineHeight: 1, borderRadius: "var(--radius)", opacity: downloading ? 1 : 0.55 }}
          >
            {downloading ? (
              <span style={{ display: "inline-block", width: 13, height: 13, border: "2px solid var(--muted)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            ) : (
              <DownloadIcon />
            )}
          </button>
        </div>
      )}
    </div>
  );
}

function SocialMediaAttachmentCard({ attachment, t }: { attachment: SocialMediaAttachment; t: ReturnType<typeof useT>["articleView"] }) {
  const { downloadFile } = useApi();
  const isInstagram = attachment.platform === "instagram";
  const isVideo = attachment.media_type === "video/mp4";
  const platformLabel = isInstagram ? "Instagram" : "X.com";
  const platformIcon = isInstagram ? "📸" : "𝕏";
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [embedCopied, setEmbedCopied] = useState(false);

  const handleCopyEmbed = useCallback(() => {
    navigator.clipboard.writeText(buildEmbedCode(attachment.post_url, attachment.platform)).then(() => {
      setEmbedCopied(true);
      setTimeout(() => setEmbedCopied(false), 2000);
    });
  }, [attachment.post_url, attachment.platform]);

  const handleDownload = useCallback(async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const proxyUrl = `/v2/download_media?url=${encodeURIComponent(attachment.media_url)}`;
      const ext = isVideo ? "mp4" : "jpg";
      const filename = `${attachment.platform}_media.${ext}`;
      await downloadFile(proxyUrl, filename);
    } catch (e: unknown) {
      setDownloadError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(false);
    }
  }, [attachment.media_url, attachment.platform, downloadFile, isVideo]);

  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "10px 12px",
      background: "var(--accent-lt)",
      border: "2px solid var(--accent)",
      borderRadius: "var(--radius)",
      fontSize: 13,
      alignItems: "flex-start",
    }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4, flexWrap: "wrap" }}>
          <span style={{ fontSize: 16, lineHeight: 1 }}>{platformIcon}</span>
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--accent)", letterSpacing: "0.04em" }}>
            {platformLabel}
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", color: "var(--fg-inverse)", background: "var(--accent)", padding: "1px 6px", borderRadius: 10, letterSpacing: "0.04em" }}>
            {t.socialMediaSourceBadge}
          </span>
        </div>
        <a href={safeHref(attachment.post_url)} target="_blank" rel="noreferrer" style={{ fontWeight: 500, color: "var(--accent)", wordBreak: "break-all", fontSize: 12 }}>
          {attachment.post_url}
        </a>
        {attachment.media_url && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
            <button
              onClick={handleDownload}
              disabled={downloading}
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: downloading ? "var(--muted)" : "var(--accent)",
                background: "var(--card-bg)",
                border: `1px solid ${downloading ? "var(--card-border)" : "var(--accent)"}`,
                borderRadius: "var(--radius)",
                padding: "3px 10px",
                cursor: downloading ? "default" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {downloading ? "⏳" : "⬇"} {isVideo ? t.socialMediaDownloadVideo : t.socialMediaDownloadPhoto}
            </button>
            {isVideo && (
              <a
                href={safeHref(attachment.media_url)}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--muted)",
                  background: "var(--card-bg)",
                  border: "1px solid var(--card-border)",
                  borderRadius: "var(--radius)",
                  padding: "3px 10px",
                  textDecoration: "none",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                ▶ {t.socialMediaOpenVideo}
              </a>
            )}
            <button
              onClick={handleCopyEmbed}
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: embedCopied ? "var(--success)" : "var(--muted)",
                background: "var(--white)",
                border: `1px solid ${embedCopied ? "var(--success)" : "var(--card-border)"}`,
                borderRadius: "var(--radius)",
                padding: "3px 10px",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {embedCopied ? (
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <CodeIcon width={11} height={11} />
              )}
              {embedCopied ? "Skopiowano" : "Embeduj"}
            </button>
            <span
              title={t.socialMediaMediaUrlWarning}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 18,
                height: 18,
                borderRadius: "50%",
                background: "#fbbf24",
                color: "var(--fg-inverse)",
                fontSize: 11,
                fontWeight: 700,
                cursor: "help",
                flexShrink: 0,
                userSelect: "none",
              }}
            >
              ?
            </span>
            {downloadError && (
              <span style={{ fontSize: 11, color: "var(--error)", marginLeft: 4 }}>
                {downloadError.includes("502") ? "Link wygasł" : downloadError}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div style={{ color: "var(--muted)", fontSize: 11 }}>{label}</div>
      <div style={{ fontWeight: 600 }}>{value}</div>
    </div>
  );
}

function InputRow({ label, value, preserveWhitespace }: { label: string; value: string; preserveWhitespace?: boolean }) {
  return (
    <div>
      <div style={{ color: "var(--muted)", fontSize: 11, marginBottom: 4 }}>{label}</div>
      <div style={{
        fontSize: 13,
        whiteSpace: preserveWhitespace ? "pre-wrap" : "normal",
        wordBreak: "break-word",
      }}>{value}</div>
    </div>
  );
}
