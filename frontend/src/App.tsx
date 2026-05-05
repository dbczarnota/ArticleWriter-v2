import { useState } from "react";
import { useAuth } from "./lib/useAuth";
import { useArticles } from "./lib/useArticles";
import { useT } from "./i18n";
import { LoginGate } from "./components/LoginGate";
import { Topbar } from "./components/Topbar";
import { Sidebar } from "./components/Sidebar";
import { ArticleView } from "./components/ArticleView";
import { NewArticleForm } from "./components/NewArticleForm";
import { SettingsView } from "./components/SettingsView";

type View = "list" | "article" | "new" | "settings";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

export default function App() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const t = useT();
  const [view, setView] = useState<View>("list");
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null);
  const [newFormKey, setNewFormKey] = useState(0);
  const {
    articles,
    loading,
    loadingMore,
    hasMore,
    dateRange,
    isFiltered,
    refresh,
    loadMore,
    setDateRange,
    markDone,
  } = useArticles();

  if (!NULL_AUTH) {
    if (isLoading) return <div style={{ padding: 32 }}>{t.app.loading}</div>;
    if (!isAuthenticated) return <LoginGate />;
  }

  function selectArticle(id: string) {
    setSelectedArticleId(id);
    setView("article");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <Topbar onSettings={() => setView("settings")} />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <Sidebar
          articles={articles}
          selectedId={selectedArticleId}
          onSelect={selectArticle}
          onNew={() => { setNewFormKey((k) => k + 1); setView("new"); }}
          currentUserId={user?.id ?? undefined}
          dateRange={dateRange}
          isFiltered={isFiltered}
          hasMore={hasMore}
          loadingMore={loadingMore}
          onDateRangeChange={setDateRange}
          onLoadMore={loadMore}
        />
        <main style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {view === "list" && (
            <p style={{ color: "var(--muted)" }}>
              {loading ? t.app.loading : t.app.selectArticleHint}
            </p>
          )}
          {view === "article" && selectedArticleId && (
            <ArticleView
              articleId={selectedArticleId}
              currentUserId={user?.id ?? undefined}
              onMarkDone={(id, done) => markDone(id, done, [user?.givenName, user?.familyName].filter(Boolean).join(" ") || user?.email || undefined)}
            />
          )}
          {view === "new" && (
            <NewArticleForm
              key={newFormKey}
              onCreated={(id) => {
                refresh();
                selectArticle(id);
              }}
            />
          )}
          {view === "settings" && <SettingsView />}
        </main>
      </div>
    </div>
  );
}
