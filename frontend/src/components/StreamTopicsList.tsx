import { useState } from "react";
import type { StreamTopic } from "../types";
import { StatusMessage } from "./ui/StatusMessage";
import { useT } from "../i18n";
import type { Translations } from "../i18n";

function buildClipboardText(topic: StreamTopic, timeRange: string): string {
  const lines: string[] = [];
  lines.push(`TEMAT: ${topic.title}`);
  lines.push(`ŹRÓDŁO: ${topic.subscription_name} | ${timeRange}`);
  if (topic.summary) {
    lines.push("", "STRESZCZENIE:", topic.summary);
  }
  if (topic.speakers.length > 0) {
    lines.push("", "ROZMÓWCY:");
    for (const s of topic.speakers) {
      lines.push(`- ${s.name_or_role}${s.description ? ` — ${s.description}` : ""}`);
    }
  }
  if (topic.facts.length > 0) {
    lines.push("", "FAKTY:");
    for (const f of topic.facts) {
      lines.push(`- ${f.text}${f.speaker ? ` [${f.speaker}]` : ""}`);
    }
  }
  if (topic.quotes.length > 0) {
    lines.push("", "CYTATY:");
    for (const q of topic.quotes) {
      lines.push(`„${q.text}"${q.speaker ? ` — ${q.speaker}` : ""}`);
    }
  }
  return lines.join("\n");
}

interface Props {
  topics: StreamTopic[];
  loading: boolean;
}

function relTime(iso: string, t: Translations): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return t.discovery.feed.justNow;
  if (min < 60) return `${min} ${t.discovery.feed.minAgo}`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}${t.discovery.feed.hAgo}`;
  return `${Math.round(h / 24)}${t.discovery.feed.dAgo}`;
}

function windowToClockRange(firstSeenAt: string, windowStartS: number, windowEndS: number): string {
  // first_seen_at ≈ when the digest ran ≈ stream_start + windowEndS
  const digestAt = new Date(firstSeenAt).getTime();
  const streamStartMs = digestAt - windowEndS * 1000;
  const startMs = streamStartMs + windowStartS * 1000;
  const endMs = streamStartMs + windowEndS * 1000;

  const fmt = (ms: number) => {
    const d = new Date(ms);
    const day = d.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
    const time = d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    return `${day}, ${time}`;
  };

  const startDate = new Date(startMs).toDateString();
  const endDate = new Date(endMs).toDateString();
  if (startDate === endDate) {
    // same day — show date once, two times
    const day = new Date(startMs).toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
    const t1 = new Date(startMs).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    const t2 = new Date(endMs).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    return `${day}, ${t1}–${t2}`;
  }
  return `${fmt(startMs)} – ${fmt(endMs)}`;
}

export function StreamTopicsList({ topics, loading }: Props) {
  const t = useT();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState<string | null>(null);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function copyToClipboard(topic: StreamTopic, timeRange: string) {
    const text = buildClipboardText(topic, timeRange);
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(topic.topic_id);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  if (loading) return <StatusMessage kind="loading">{t.streams.topic.loading}</StatusMessage>;
  if (topics.length === 0)
    return <StatusMessage kind="empty">{t.streams.topic.noTopics}</StatusMessage>;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 8 }}>
      {topics.map((topic) => {
        const isOpen = expanded.has(topic.topic_id);
        const isCopied = copied === topic.topic_id;
        const timeRange = windowToClockRange(
          topic.first_seen_at,
          topic.window_start_seconds,
          topic.window_end_seconds,
        );
        return (
          <div
            key={topic.topic_id}
            style={{
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              background: "var(--white)",
              overflow: "hidden",
            }}
          >
            {/* Header — always visible, click to expand */}
            <button
              type="button"
              onClick={() => toggle(topic.topic_id)}
              style={{
                width: "100%",
                textAlign: "left",
                background: "none",
                border: "none",
                padding: "12px 16px",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              {/* Row 1: badge + title + copy + time + chevron */}
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    fontSize: 10,
                    padding: "2px 7px",
                    borderRadius: 999,
                    flexShrink: 0,
                    background: topic.is_news ? "var(--accent-lt)" : "var(--bg)",
                    color: topic.is_news ? "var(--accent)" : "var(--muted)",
                    border: `1px solid ${topic.is_news ? "var(--accent)" : "var(--border)"}`,
                  }}
                >
                  {topic.is_news ? t.streams.topic.newsBadge : t.streams.topic.notNewsBadge}
                </span>
                <span style={{ fontWeight: 600, color: "var(--text)", flex: 1, fontSize: 14 }}>
                  {topic.title}
                </span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); copyToClipboard(topic, timeRange); }}
                  style={{
                    flexShrink: 0,
                    fontSize: 11,
                    padding: "2px 8px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    background: isCopied ? "var(--success-fg)" : "var(--bg)",
                    color: isCopied ? "white" : "var(--muted)",
                    cursor: "pointer",
                    transition: "background 0.15s",
                  }}
                >
                  {isCopied ? "✓ Skopiowano" : "Kopiuj"}
                </button>
                <span style={{ fontSize: 11, color: "var(--muted)", flexShrink: 0 }}>
                  {relTime(topic.last_seen_at, t)}
                </span>
                <span style={{ fontSize: 13, color: "var(--muted)", flexShrink: 0 }}>
                  {isOpen ? "▲" : "▼"}
                </span>
              </div>

              {/* Row 2: source + time window */}
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--accent)",
                    background: "var(--accent-lt)",
                    borderRadius: 4,
                    padding: "1px 7px",
                  }}
                >
                  {topic.subscription_name}
                </span>
                <span style={{ fontSize: 11, color: "var(--muted)" }}>
                  {timeRange}
                </span>
              </div>

              {/* Row 3: summary preview (collapsed only) */}
              {!isOpen && topic.summary && (
                <p
                  style={{
                    margin: 0,
                    fontSize: 13,
                    color: "var(--text)",
                    lineHeight: 1.5,
                    overflow: "hidden",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                  }}
                >
                  {topic.summary}
                </p>
              )}
            </button>

            {/* Expanded detail */}
            {isOpen && (
              <div
                style={{
                  borderTop: "1px solid var(--border)",
                  padding: "14px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                  background: "var(--bg)",
                }}
              >
                {/* Summary */}
                {topic.summary && (
                  <p style={{ margin: 0, fontSize: 13, color: "var(--text)", lineHeight: 1.6 }}>
                    {topic.summary}
                  </p>
                )}

                {/* Speakers */}
                {topic.speakers.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                      Rozmówcy
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                      {topic.speakers.map((s, i) => (
                        <div key={i} style={{ fontSize: 13, color: "var(--text)" }}>
                          <strong>{s.name_or_role}</strong>
                          {s.description && (
                            <span style={{ color: "var(--muted)" }}> — {s.description}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Facts */}
                {topic.facts.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                      Fakty
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
                      {topic.facts.map((f, i) => (
                        <li key={i} style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
                          {f.text}
                          {f.speaker && (
                            <span style={{ color: "var(--muted)", fontSize: 11 }}> [{f.speaker}]</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Quotes */}
                {topic.quotes.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                      Cytaty
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {topic.quotes.map((q, i) => (
                        <blockquote
                          key={i}
                          style={{
                            margin: 0,
                            paddingLeft: 12,
                            borderLeft: "3px solid var(--accent)",
                            fontSize: 13,
                            color: "var(--text)",
                            lineHeight: 1.5,
                            fontStyle: "italic",
                          }}
                        >
                          „{q.text}"
                          {q.speaker && (
                            <span style={{ display: "block", fontSize: 11, color: "var(--muted)", fontStyle: "normal", marginTop: 2 }}>
                              — {q.speaker}
                            </span>
                          )}
                        </blockquote>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
