import { useState } from "react";
import { useAuth } from "./lib/useAuth";
import { useArticles } from "./lib/useArticles";
import { LoginGate } from "./components/LoginGate";
import { Topbar } from "./components/Topbar";
import { Sidebar } from "./components/Sidebar";
import { ArticleView } from "./components/ArticleView";
import { NewArticleForm } from "./components/NewArticleForm";
import { SettingsView } from "./components/SettingsView";

type View = "list" | "article" | "new" | "settings";

const NULL_AUTH = import.meta.env.VITE_AUTH_BACKEND === "null";

export default function App() {
  const { isAuthenticated, isLoading } = useAuth();
  const [view, setView] = useState<View>("list");
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null);
  const { articles, loading, refresh } = useArticles();

  if (!NULL_AUTH) {
    if (isLoading) return <div style={{ padding: 32 }}>Ładowanie…</div>;
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
          onNew={() => setView("new")}
        />
        <main style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {view === "list" && (
            <p style={{ color: "var(--muted)" }}>
              {loading ? "Ładowanie…" : "Wybierz artykuł lub utwórz nowy."}
            </p>
          )}
          {view === "article" && selectedArticleId && (
            <ArticleView articleId={selectedArticleId} />
          )}
          {view === "new" && (
            <NewArticleForm
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
