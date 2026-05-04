export interface ArticleListItem {
  id: string;
  topic: string;
  status: "running" | "done" | "failed" | "insufficient_sources";
  pipeline_stage: string | null;
  marked_done: boolean;
  domain_name: string;
  author_user_id: string;
  author_email: string | null;
  created_at: string | null;
  completed_at: string | null;
  total_duration_ms: number | null;
}

export interface Fact {
  id: string;
  text: string;
  context: string | null;
  source_url: string | null;
  source_title: string | null;
  was_used: boolean;
}

export interface Quote {
  id: string;
  text: string;
  speaker: string | null;
  context: string | null;
  source_url: string | null;
  was_used: boolean;
}

export interface EmbedCandidate {
  id: string;
  url: string;
  title: string | null;
  source: string;
  thumbnail_url: string | null;
  description: string | null;
  channel: string | null;
  competitor_source_url: string | null;
}

export interface UsageEvent {
  id: string;
  agent_name: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
  occurred_at: string | null;
}

export interface FallbackEvent {
  id: string;
  agent_name: string;
  failed_model: string;
  error_type: string;
  error_message: string | null;
  occurred_at: string | null;
}

export interface Article extends ArticleListItem {
  org_code: string;
  marked_done_by_name: string | null;
  html: string | null;
  alternative_titles: string[];
  followup_topics: string[];
  sources: string[];
  pipeline_timing: Record<string, number>;
  errors: Array<Record<string, string>>;
  insufficient_sources_detail: Record<string, unknown> | null;
  facts: Fact[];
  quotes: Quote[];
  embed_candidates: EmbedCandidate[];
  usage_events: UsageEvent[];
  fallback_events: FallbackEvent[];
}

export interface DomainConfigData {
  org_code: string;
  description: string;
  language: string;
  target_word_count: number;
  max_facts: number;
  max_quotes: number;
  search_freshness: string;
  num_queries: number;
  max_results: number;
  min_source_signals: number;
  max_pages_to_scrape: number;
  youtube_search: boolean;
  twitter_search: boolean;
  facebook_search: boolean;
  news_search: boolean;
  tiktok_search: boolean;
  instagram_search: boolean;
  reddit_search: boolean;
  media_search_languages: string[];
  media_search_num: number;
  media_search_max_query_tiers: number;
  youtube_sort_by_date: boolean;
  reflection_context_articles: number;
  guidelines: string;
  html_format: string;
  reflection_stance: string;
  reflection_rounds: number;
  example_articles: string[];
  example_titles: string[];
  agent_models: Record<string, string>;
  agent_fallback_models: Record<string, string[]>;
  updated_at: string | null;
}
