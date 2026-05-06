import { useState } from "react";
import { useAuth } from "./lib/useAuth";
import { useArticles } from "./lib/useArticles";
import { useMediaQuery } from "./lib/useMediaQuery";
import { useT } from "./i18n";
import { LoginGate } from "./components/LoginGate";
import { Topbar } from "./components/Topbar";
import { Sidebar } from "./components/Sidebar";
import { ArticleView } from "./components/ArticleView";
import { NewArticleForm } from "./components/NewArticleForm";
import { SettingsView } from "./components/SettingsView";
import { DiscoveryHub } from "./components/DiscoveryHub";

type View = "list" | "article" | "new" | "settings" | "discovery";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

export default function App() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const t = useT();
  const isMobile = useMediaQuery("(max-width: 767px)");
  const [view, setView] = useState<View>("list");
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null);
  const [newFormKey, setNewFormKey] = useState(0);
  // Default: open on desktop, closed on mobile (drawer must not cover content
  // out of the gate). The user toggles via the hamburger in Topbar.
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
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
    // Mobile: tapping an article should close the drawer so the article is
    // visible. Desktop: keep the sidebar as it was.
    if (isMobile) setSidebarOpen(false);
    // Refresh the list whenever the user navigates so co-workers' new
    // articles show up without needing a tab switch.
    refresh();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <Topbar
        onSettings={() => setView("settings")}
        onDiscovery={() => setView("discovery")}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        sidebarOpen={sidebarOpen}
      />
      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        <Sidebar
          articles={articles}
          selectedId={selectedArticleId}
          onSelect={selectArticle}
          onNew={() => {
            setNewFormKey((k) => k + 1);
            setView("new");
            if (isMobile) setSidebarOpen(false);
            refresh();
          }}
          currentUserId={user?.id ?? undefined}
          dateRange={dateRange}
          isFiltered={isFiltered}
          hasMore={hasMore}
          loadingMore={loadingMore}
          onDateRangeChange={setDateRange}
          onLoadMore={loadMore}
          open={sidebarOpen}
          isMobile={isMobile}
          onClose={() => setSidebarOpen(false)}
          onExpand={() => setSidebarOpen(true)}
        />
        <main style={{ flex: 1, overflow: "auto", padding: isMobile ? 12 : 24 }}>
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
          {view === "discovery" && <DiscoveryHub />}
        </main>
      </div>
    </div>
  );
}
