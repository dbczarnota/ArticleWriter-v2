import type { DiscoveryTopicSummary } from "../types";
import { TopicCard } from "./TopicCard";
import { StatusMessage } from "./ui/StatusMessage";
import { useT } from "../i18n";

interface Props {
  topics: DiscoveryTopicSummary[];
  loading: boolean;
  onWrite: (topicId: string) => void;
  onSelect?: (topicId: string) => void;
  onDismiss?: (topicId: string) => void;
  onRestore?: (topicId: string) => void;
}

export function TopicsList({ topics, loading, onWrite, onSelect, onDismiss, onRestore }: Props) {
  const t = useT();
  if (loading) return <StatusMessage kind="loading">{t.discovery.topic.loading}</StatusMessage>;
  if (topics.length === 0) return <StatusMessage kind="empty">{t.discovery.topic.empty}</StatusMessage>;
  return (
    <div>
      {topics.map((topic) => (
        <TopicCard
          key={topic.id}
          topic={topic}
          onWrite={onWrite}
          onSelect={onSelect}
          onDismiss={onDismiss}
          onRestore={onRestore}
        />
      ))}
    </div>
  );
}
