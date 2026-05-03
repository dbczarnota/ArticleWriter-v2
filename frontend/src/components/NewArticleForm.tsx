// frontend/src/components/NewArticleForm.tsx
import { useState } from "react";
import { useArticles } from "../lib/useArticles";

interface NewArticleFormProps {
  onCreated: (articleId: string) => void;
}

export function NewArticleForm({ onCreated }: NewArticleFormProps) {
  const { submitArticle } = useArticles();
  const [topic, setTopic] = useState("");
  const [instructions, setInstructions] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [writerModel, setWriterModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const urls = urlsText.split("\n").map((u) => u.trim()).filter(Boolean);
      const agents: Record<string, Record<string, unknown>> = {};
      if (writerModel) agents["writer"] = { model: writerModel };
      const result = await submitArticle({
        topic: topic.trim(),
        additional_instructions: instructions.trim() || undefined,
        urls: urls.length > 0 ? urls : undefined,
        agents: Object.keys(agents).length > 0 ? agents : undefined,
      });
      onCreated(result.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 10px",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    fontSize: 13,
    fontFamily: "var(--font)",
    background: "var(--white)",
    color: "var(--text)",
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20 }}>Nowy artykuł</h2>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
            Temat *
          </label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="np. Najnowsze plotki o..."
            required
            style={inputStyle}
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
            Dodatkowe wskazówki
          </label>
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
            placeholder="Skup się na..."
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
            URL-e (jeden na linię)
          </label>
          <textarea
            value={urlsText}
            onChange={(e) => setUrlsText(e.target.value)}
            rows={3}
            placeholder="https://..."
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace" }}
          />
        </div>

        <div>
          <button
            type="button"
            onClick={() => setAdvancedOpen((o) => !o)}
            style={{ background: "none", border: "none", fontSize: 13, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}
          >
            <span style={{ fontSize: 10 }}>{advancedOpen ? "▼" : "▶"}</span>
            Zaawansowane
          </button>
          {advancedOpen && (
            <div style={{ marginTop: 12, paddingLeft: 16 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 4 }}>Model pisarza</label>
              <input value={writerModel} onChange={(e) => setWriterModel(e.target.value)} placeholder="np. gemini-2.0-flash (domyślny)" style={inputStyle} />
            </div>
          )}
        </div>

        {error && <p style={{ color: "#ef4444", fontSize: 13 }}>{error}</p>}

        <button
          type="submit"
          disabled={loading || !topic.trim()}
          style={{
            padding: "10px 20px",
            background: loading || !topic.trim() ? "var(--border)" : "var(--accent)",
            color: loading || !topic.trim() ? "var(--muted)" : "var(--white)",
            border: "none",
            borderRadius: "var(--radius)",
            fontSize: 14,
            fontWeight: 500,
            alignSelf: "flex-start",
            cursor: loading || !topic.trim() ? "default" : "pointer",
          }}
        >
          {loading ? "Generuję artykuł…" : "Generuj"}
        </button>
      </form>
    </div>
  );
}
