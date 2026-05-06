import type { DiscoveryTopicSummary } from "../types";
import { TopicCard } from "./TopicCard";

interface Props {
  topics: DiscoveryTopicSummary[];
  loading: boolean;
  onWrite: (topicId: string) => void;
  onSelect?: (topicId: string) => void;
}

export function TopicsList({ topics, loading, onWrite, onSelect }: Props) {
  if (loading) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>Ładowanie…</div>;
  }
  if (topics.length === 0) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>Brak tematów dla tego filtra.</div>;
  }
  return (
    <div>
      {topics.map((t) => (
        <TopicCard key={t.id} topic={t} onWrite={onWrite} onSelect={onSelect} />
      ))}
    </div>
  );
}
