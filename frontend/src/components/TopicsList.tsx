import type { DiscoveryTopicSummary } from "../types";
import { TopicCard } from "./TopicCard";
import { useT } from "../i18n";

interface Props {
  topics: DiscoveryTopicSummary[];
  loading: boolean;
  onWrite: (topicId: string) => void;
  onSelect?: (topicId: string) => void;
}

export function TopicsList({ topics, loading, onWrite, onSelect }: Props) {
  const t = useT();
  if (loading) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>{t.discovery.topic.loading}</div>;
  }
  if (topics.length === 0) {
    return <div style={{ padding: 24, color: "var(--muted)" }}>{t.discovery.topic.empty}</div>;
  }
  return (
    <div>
      {topics.map((topic) => (
        <TopicCard key={topic.id} topic={topic} onWrite={onWrite} onSelect={onSelect} />
      ))}
    </div>
  );
}
