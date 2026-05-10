import { useEffect, useState } from "react";
import type { StreamTopic } from "../types";
import { useApi } from "../lib/useApi";

interface Props {
  streamTopicId: string;
  onClose: () => void;
}

function formatWindow(w: { start_at: string; end_at: string }): string {
  const start = new Date(w.start_at);
  const end = new Date(w.end_at);
  const day = start.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
  const t1 = start.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  const t2 = end.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  return `${day}, ${t1}–${t2}`;
}

export function StreamSourceModal({ streamTopicId, onClose }: Props) {
  const { request } = useApi();
  const [topic, setTopic] = useState<StreamTopic | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    request(`/v2/streams/topics/${streamTopicId}`)
      .then((data) => setTopic(data as StreamTopic))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [streamTopicId]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.45)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--white)", borderRadius: "var(--radius)",
          boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
          width: 560, maxWidth: "95vw", maxHeight: "80vh",
          overflow: "auto", padding: 24,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {loading && <div style={{ color: "var(--muted)", fontSize: 13 }}>Ładowanie…</div>}
        {!loading && !topic && <div style={{ color: "var(--muted)", fontSize: 13 }}>Nie znaleziono.</div>}
        {topic && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--accent)", background: "var(--accent-lt)", borderRadius: 4, padding: "1px 7px", display: "inline-block", marginBottom: 6 }}>
                  {topic.subscription_name}
                </div>
                <div style={{ fontWeight: 600, fontSize: 15, color: "var(--text)" }}>{topic.title}</div>
                {topic.windows.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                    {topic.windows.map(formatWindow).join(" · ")}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                style={{ flexShrink: 0, background: "none", border: "none", cursor: "pointer", color: "var(--muted)", fontSize: 18, lineHeight: 1 }}
              >
                ✕
              </button>
            </div>

            {/* Summary */}
            {topic.summary && (
              <p style={{ margin: 0, fontSize: 13, color: "var(--text)", lineHeight: 1.6 }}>
                {topic.summary}
              </p>
            )}

            {/* Speakers */}
            {topic.speakers.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Rozmówcy</div>
                {topic.speakers.map((s, i) => (
                  <div key={i} style={{ fontSize: 13, color: "var(--text)" }}>
                    <strong>{s.name_or_role}</strong>
                    {s.description && <span style={{ color: "var(--muted)" }}> — {s.description}</span>}
                  </div>
                ))}
              </div>
            )}

            {/* Facts */}
            {topic.facts.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Fakty</div>
                <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
                  {topic.facts.map((f, i) => (
                    <li key={i} style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
                      {f.text}{f.speaker && <span style={{ color: "var(--muted)", fontSize: 11 }}> [{f.speaker}]</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Quotes */}
            {topic.quotes.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Cytaty</div>
                {topic.quotes.map((q, i) => (
                  <blockquote key={i} style={{ margin: 0, paddingLeft: 12, borderLeft: "3px solid var(--accent)", fontSize: 13, color: "var(--text)", lineHeight: 1.5, fontStyle: "italic" }}>
                    „{q.text}"
                    {q.speaker && <span style={{ display: "block", fontSize: 11, color: "var(--muted)", fontStyle: "normal", marginTop: 2 }}>— {q.speaker}</span>}
                  </blockquote>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
