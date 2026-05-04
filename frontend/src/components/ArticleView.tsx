import { useEffect, useState } from "react";
import type { Article, Fact, Quote } from "../types";
import { useArticles } from "../lib/useArticles";
import { CollapsibleSection } from "./CollapsibleSection";

interface ArticleViewProps {
  articleId: string;
  currentUserId?: string;
  onMarkDone?: (id: string, done: boolean) => Promise<void>;
}

export function ArticleView({ articleId, currentUserId, onMarkDone }: ArticleViewProps) {
  const { fetchArticle } = useArticles();
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

  if (error) return <p style={{ color: "#ef4444" }}>Błąd: {error}</p>;
  if (!article) return <p style={{ color: "var(--muted)" }}>Ładowanie…</p>;

  const STAGE_LABELS: Record<string, string> = {
    search: "Wyszukiwanie wyników…",
    scraping: "Scrapowanie stron…",
    parsing: "Parsowanie artykułów…",
    extraction: "Ekstrakcja faktów i cytatów…",
    adaptive_search: "Dodatkowe wyszukiwanie…",
    media_search: "Wyszukiwanie social media…",
    instructions: "Przygotowanie instrukcji…",
    writer: "Pisanie artykułu…",
    reflection: "Recenzja i korekta…",
    followup: "Tematy follow-up…",
  };

  if (article.status === "running") {
    const stageLabel = article.pipeline_stage ? (STAGE_LABELS[article.pipeline_stage] ?? article.pipeline_stage) : "Generowanie artykułu…";
    return (
      <div>
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
  const usedSources = article.sources;
  // TODO(sources): approximate — only covers fact.source_url, not quote.source_url
  const unusedSourceUrls = article.facts
    .filter((f) => !f.was_used && f.source_url)
    .map((f) => f.source_url as string)
    .filter((url) => !usedSources.includes(url));
  const uniqueUnused = [...new Set(unusedSourceUrls)];

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

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20, gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 6 }}>{article.topic}</h2>
          <div style={{ display: "flex", gap: 16, fontSize: 12, color: "var(--muted)", flexWrap: "wrap", alignItems: "center" }}>
            <span>
              {article.author_email
                ? (currentUserId && article.author_user_id === currentUserId
                    ? `Ty (${article.author_email.split("@")[0]})`
                    : article.author_email.split("@")[0])
                : (currentUserId && article.author_user_id === currentUserId ? "Ty" : "—")}
            </span>
            <span>{article.created_at ? new Date(article.created_at).toLocaleString("pl") : "—"}</span>
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
                style={{ width: 14, height: 14, accentColor: "#22c55e", cursor: "pointer" }}
              />
              <span style={{ fontWeight: article.marked_done ? 600 : 400, color: article.marked_done ? "#22c55e" : "var(--muted)" }}>
                {article.marked_done ? "Done ✓" : "Done"}
              </span>
              {article.marked_done && article.marked_done_by_name && (
                <span style={{ color: "var(--muted)", fontSize: 11 }}>
                  przez {article.marked_done_by_name}
                </span>
              )}
            </label>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button
            onClick={handleCopy}
            title="Kopiuj HTML do schowka"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 14px",
              background: copied ? "#22c55e" : "var(--white)",
              color: copied ? "#fff" : "var(--accent)",
              border: `1px solid ${copied ? "#22c55e" : "var(--accent)"}`,
              borderRadius: "var(--radius)",
              fontSize: 13,
              cursor: "pointer",
              transition: "background 0.15s, color 0.15s, border-color 0.15s",
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            {copied ? "Skopiowano!" : "Kopiuj HTML"}
          </button>
          <button
            onClick={handleExport}
            style={{
              padding: "6px 14px",
              background: "var(--accent)",
              color: "var(--white)",
              border: "none",
              borderRadius: "var(--radius)",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Eksport HTML
          </button>
        </div>
      </div>

      {/* Article HTML */}
      {article.html && (
        <div
          className="article-html"
          dangerouslySetInnerHTML={{ __html: article.html }}
          style={{
            padding: 20,
            background: "var(--white)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            marginBottom: 24,
            lineHeight: 1.7,
          }}
        />
      )}

      {/* Alternative titles */}
      {article.alternative_titles.length > 0 && (
        <CollapsibleSection prominent title="Alternatywne tytuły" count={article.alternative_titles.length} defaultOpen>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {article.alternative_titles.map((title, i) => (
              <div key={i} style={{ padding: "8px 12px", background: "var(--white)", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: 13 }}>
                {title}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Follow-up topics */}
      {article.followup_topics.length > 0 && (
        <CollapsibleSection prominent title="Tematy na follow-up" count={article.followup_topics.length} defaultOpen>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {article.followup_topics.map((topic, i) => (
              <span key={i} style={{ padding: "5px 10px", background: "var(--accent-lt)", border: "1px solid #fed7aa", borderRadius: 20, fontSize: 12, color: "var(--accent)", fontWeight: 500 }}>
                {topic}
              </span>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Social media embeds */}
      {article.embed_candidates.length > 0 && (
        <CollapsibleSection prominent title="Social media" count={article.embed_candidates.length}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {[...article.embed_candidates].sort((a, b) => (b.competitor_source_url ? 1 : 0) - (a.competitor_source_url ? 1 : 0)).map((e) => (
              <div key={e.id} style={{ display: "flex", gap: 10, padding: "8px 12px", background: e.competitor_source_url ? "#fffbeb" : "var(--white)", border: `1px solid ${e.competitor_source_url ? "#f59e0b" : "var(--border)"}`, borderRadius: "var(--radius)", fontSize: 13, alignItems: "flex-start" }}>
                {e.thumbnail_url && <img src={e.thumbnail_url} alt="" onError={(ev) => { (ev.target as HTMLImageElement).style.display = "none"; }} style={{ width: 64, height: 48, objectFit: "cover", borderRadius: 4, flexShrink: 0 }} />}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 2, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", color: "var(--muted)" }}>{e.source}</span>
                    {e.channel && <span style={{ fontSize: 11, color: "var(--muted)" }}>· {e.channel}</span>}
                    {e.competitor_source_url && (
                      <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", color: "#b45309", background: "#fef3c7", padding: "1px 5px", borderRadius: 3, letterSpacing: "0.04em" }}>
                        ★ u konkurencji
                      </span>
                    )}
                  </div>
                  <a href={e.url} target="_blank" rel="noreferrer" style={{ fontWeight: 500, color: "var(--accent)", wordBreak: "break-word" }}>
                    {e.title ?? e.url}
                  </a>
                  {e.description && <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 2, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{e.description}</p>}
                  {e.competitor_source_url && (
                    <p style={{ fontSize: 11, color: "#92400e", marginTop: 4 }}>
                      źródło: <a href={e.competitor_source_url} target="_blank" rel="noreferrer" style={{ color: "#92400e", textDecoration: "underline", wordBreak: "break-all" }}>{e.competitor_source_url}</a>
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Facts */}
      <CollapsibleSection prominent title="Fakty użyte" count={usedFacts.length} defaultOpen>
        {usedFacts.map((f) => (
          <FactCard key={f.id} fact={f} />
        ))}
        <CollapsibleSection title="Odrzucone fakty" count={rejectedFacts.length}>
          {rejectedFacts.map((f) => (
            <FactCard key={f.id} fact={f} muted />
          ))}
        </CollapsibleSection>
      </CollapsibleSection>

      {/* Quotes */}
      <CollapsibleSection prominent title="Cytaty użyte" count={usedQuotes.length} defaultOpen>
        {usedQuotes.map((q) => (
          <QuoteCard key={q.id} quote={q} />
        ))}
        <CollapsibleSection title="Odrzucone cytaty" count={rejectedQuotes.length}>
          {rejectedQuotes.map((q) => (
            <QuoteCard key={q.id} quote={q} muted />
          ))}
        </CollapsibleSection>
      </CollapsibleSection>

      {/* Sources */}
      <CollapsibleSection prominent title="Źródła użyte" count={usedSources.length} defaultOpen>
        {usedSources.map((url) => (
          <div key={url} style={{ borderLeft: "3px solid #22c55e", paddingLeft: 10, marginBottom: 6, fontSize: 13 }}>
            <a href={url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", wordBreak: "break-all" }}>{url}</a>
          </div>
        ))}
        <CollapsibleSection title="Nieużyte źródła" count={uniqueUnused.length}>
          {uniqueUnused.map((url) => (
            <div key={url} style={{ borderLeft: "3px solid var(--border)", paddingLeft: 10, marginBottom: 6, fontSize: 13 }}>
              <a href={url} target="_blank" rel="noreferrer" style={{ color: "var(--muted)", wordBreak: "break-all" }}>{url}</a>
            </div>
          ))}
        </CollapsibleSection>
      </CollapsibleSection>

      {/* Stats */}
      <CollapsibleSection prominent title="Statystyki pipeline">
        <div style={{ padding: "8px 0", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, fontSize: 13 }}>
          <Stat label="Fakty" value={article.facts.length} />
          <Stat label="Cytaty" value={article.quotes.length} />
          <Stat label="Embeds" value={article.embed_candidates.length} />
          <Stat label="Wywołania agentów" value={article.usage_events.length} />
          <Stat label="Tokeny" value={totalTokens.toLocaleString()} />
          <Stat label="Czas (s)" value={article.total_duration_ms != null ? (article.total_duration_ms / 1000).toFixed(1) : "—"} />
        </div>
      </CollapsibleSection>
    </div>
  );
}

function FactCard({ fact, muted }: { fact: Fact; muted?: boolean }) {
  return (
    <div style={{
      borderLeft: `3px solid ${muted ? "var(--border)" : "var(--accent)"}`,
      marginBottom: 8,
      background: muted ? "transparent" : "var(--accent-lt)",
      borderRadius: "0 var(--radius) var(--radius) 0",
      padding: "8px 8px 8px 12px",
    }}>
      <p style={{ fontSize: 13, marginBottom: 4 }}>{fact.text}</p>
      {fact.context && <p style={{ fontSize: 12, color: "var(--muted)" }}>{fact.context}</p>}
      {fact.source_url && (
        <a href={fact.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "var(--accent)" }}>
          {fact.source_title ?? fact.source_url}
        </a>
      )}
    </div>
  );
}

function QuoteCard({ quote, muted }: { quote: Quote; muted?: boolean }) {
  return (
    <div style={{
      borderLeft: `3px solid ${muted ? "var(--border)" : "var(--accent)"}`,
      padding: "8px 8px 8px 12px",
      marginBottom: 8,
      background: muted ? "transparent" : "var(--accent-lt)",
      borderRadius: "0 var(--radius) var(--radius) 0",
    }}>
      <p style={{ fontSize: 13, fontStyle: "italic" }}>"{quote.text}"</p>
      {quote.speaker && <p style={{ fontSize: 12, fontWeight: 500, marginTop: 4 }}>— {quote.speaker}</p>}
      {quote.context && <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{quote.context}</p>}
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
