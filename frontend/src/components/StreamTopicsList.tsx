import type { StreamTopic } from "../types";
import { StatusMessage } from "./ui/StatusMessage";
import { useT } from "../i18n";
import type { Translations } from "../i18n";

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

export function StreamTopicsList({ topics, loading }: Props) {
  const t = useT();

  if (loading) return <StatusMessage kind="loading">{t.streams.topic.loading}</StatusMessage>;
  if (topics.length === 0)
    return <StatusMessage kind="empty">{t.streams.topic.noTopics}</StatusMessage>;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12 }}>
      {topics.map((topic) => (
        <div
          key={topic.topic_id}
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: 16,
            background: "var(--white)",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 6 }}>
            <span
              style={{
                fontSize: 11,
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
            <span style={{ fontWeight: 600, color: "var(--text)", flex: 1 }}>{topic.title}</span>
            <span style={{ fontSize: 11, color: "var(--muted)", flexShrink: 0 }}>
              {t.streams.topic.lastSeen}: {relTime(topic.last_seen_at, t)}
            </span>
          </div>
          {topic.summary && (
            <p style={{ margin: 0, fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
              {topic.summary}
            </p>
          )}
          {topic.speakers.length > 0 && (
            <p style={{ margin: "6px 0 0", fontSize: 11, color: "var(--muted)" }}>
              {topic.speakers.map((s) => s.name_or_role).join(", ")}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
