import { useEffect, useState } from "react";
import type { Article, Fact, Quote } from "../types";
import { useArticles } from "../lib/useArticles";
import { CollapsibleSection } from "./CollapsibleSection";

interface ArticleViewProps {
  articleId: string;
}

export function ArticleView({ articleId }: ArticleViewProps) {
  const { fetchArticle } = useArticles();
  const [article, setArticle] = useState<Article | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  if (article.status === "running") {
    return (
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>{article.topic}</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)", fontSize: 14 }}>
          <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          Generowanie artykułu…
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

  function handleExport() {
    const a0 = article;
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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>{article.topic}</h2>
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
        <section style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Alternatywne tytuły</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {article.alternative_titles.map((title, i) => (
              <div key={i} style={{
                padding: "8px 12px",
                background: "var(--white)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                fontSize: 13,
              }}>
                {title}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Follow-up topics */}
      {article.followup_topics.length > 0 && (
        <section style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Tematy na follow-up</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {article.followup_topics.map((topic, i) => (
              <span key={i} style={{
                padding: "5px 10px",
                background: "var(--accent-lt)",
                border: "1px solid #fed7aa",
                borderRadius: 20,
                fontSize: 12,
                color: "var(--accent)",
                fontWeight: 500,
              }}>
                {topic}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Facts */}
      <section>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          Fakty użyte ({usedFacts.length})
        </h3>
        {usedFacts.map((f) => (
          <FactCard key={f.id} fact={f} />
        ))}
        <CollapsibleSection title="Odrzucone fakty" count={rejectedFacts.length}>
          {rejectedFacts.map((f) => (
            <FactCard key={f.id} fact={f} muted />
          ))}
        </CollapsibleSection>
      </section>

      {/* Quotes */}
      <section style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          Cytaty użyte ({usedQuotes.length})
        </h3>
        {usedQuotes.map((q) => (
          <QuoteCard key={q.id} quote={q} />
        ))}
        <CollapsibleSection title="Odrzucone cytaty" count={rejectedQuotes.length}>
          {rejectedQuotes.map((q) => (
            <QuoteCard key={q.id} quote={q} muted />
          ))}
        </CollapsibleSection>
      </section>

      {/* Sources */}
      <section style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          Źródła użyte ({usedSources.length})
        </h3>
        {usedSources.map((url) => (
          <div key={url} style={{ borderLeft: "3px solid #22c55e", paddingLeft: 10, marginBottom: 6, fontSize: 13 }}>
            <a href={url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", wordBreak: "break-all" }}>
              {url}
            </a>
          </div>
        ))}
        <CollapsibleSection title="Nieużyte źródła" count={uniqueUnused.length}>
          {uniqueUnused.map((url) => (
            <div key={url} style={{ borderLeft: "3px solid var(--border)", paddingLeft: 10, marginBottom: 6, fontSize: 13 }}>
              <a href={url} target="_blank" rel="noreferrer" style={{ color: "var(--muted)", wordBreak: "break-all" }}>{url}</a>
            </div>
          ))}
        </CollapsibleSection>
      </section>

      {/* Stats */}
      <section style={{ marginTop: 24, padding: 16, background: "var(--sidebar)", borderRadius: "var(--radius)", fontSize: 13 }}>
        <h3 style={{ fontWeight: 600, marginBottom: 8 }}>Statystyki pipeline</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
          <Stat label="Fakty" value={article.facts.length} />
          <Stat label="Cytaty" value={article.quotes.length} />
          <Stat label="Embeds" value={article.embed_candidates.length} />
          <Stat label="Wywołania agentów" value={article.usage_events.length} />
          <Stat label="Tokeny" value={totalTokens.toLocaleString()} />
          <Stat label="Czas (s)" value={article.total_duration_ms != null ? (article.total_duration_ms / 1000).toFixed(1) : "—"} />
        </div>
      </section>
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
