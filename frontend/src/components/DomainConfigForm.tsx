// frontend/src/components/DomainConfigForm.tsx
import { useState } from "react";
import type { DomainConfigData } from "../types";

const MEDIA_TOGGLES: Array<{ key: keyof DomainConfigData; label: string }> = [
  { key: "youtube_search", label: "YouTube" },
  { key: "twitter_search", label: "Twitter/X" },
  { key: "tiktok_search", label: "TikTok" },
  { key: "instagram_search", label: "Instagram" },
  { key: "reddit_search", label: "Reddit" },
  { key: "news_search", label: "News" },
  { key: "facebook_search", label: "Facebook" },
];

const FRESHNESS_OPTIONS = [
  { value: "qdr:d", label: "Ostatni dzień" },
  { value: "qdr:w", label: "Ostatni tydzień" },
  { value: "qdr:m", label: "Ostatni miesiąc" },
  { value: "qdr:y", label: "Ostatni rok" },
];

interface DomainConfigFormProps {
  initialConfig: DomainConfigData;
  activeSection: string;
  saving: boolean;
  error: string | null;
  onSave: (config: DomainConfigData) => void;
}

export function DomainConfigForm({ initialConfig, activeSection, saving, error, onSave }: DomainConfigFormProps) {
  const [form, setForm] = useState<DomainConfigData>(initialConfig);

  function set<K extends keyof DomainConfigData>(key: K, value: DomainConfigData[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function sectionVisible(id: string) {
    return activeSection === id;
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

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: 12,
    fontWeight: 500,
    marginBottom: 4,
    color: "var(--muted)",
  };

  return (
    <div style={{ flex: 1 }}>
      <div style={{ paddingBottom: 80 }}>
        {/* Podstawowe */}
        <section id="podstawowe" style={{ display: sectionVisible("podstawowe") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Podstawowe</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={labelStyle}>Opis domeny</label>
              <textarea value={form.description} onChange={(e) => set("description", e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical" }} />
            </div>
            <div>
              <label style={labelStyle}>Język artykułów</label>
              <input value={form.language} onChange={(e) => set("language", e.target.value)} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Wyszukiwanie */}
        <section id="wyszukiwanie" style={{ display: sectionVisible("wyszukiwanie") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Wyszukiwanie</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Docelowa długość (słów)</label>
              <input type="number" value={form.target_word_count} onChange={(e) => set("target_word_count", +e.target.value)} min={100} max={5000} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Świeżość wyników</label>
              <select value={form.search_freshness} onChange={(e) => set("search_freshness", e.target.value)} style={inputStyle}>
                {FRESHNESS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Liczba zapytań</label>
              <input type="number" value={form.num_queries} onChange={(e) => set("num_queries", +e.target.value)} min={1} max={10} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Max wyników / zapytanie</label>
              <input type="number" value={form.max_results} onChange={(e) => set("max_results", +e.target.value)} min={1} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Min sygnałów źródłowych</label>
              <input type="number" value={form.min_source_signals} onChange={(e) => set("min_source_signals", +e.target.value)} min={0} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Max stron do scrapowania</label>
              <input type="number" value={form.max_pages_to_scrape} onChange={(e) => set("max_pages_to_scrape", +e.target.value)} min={1} max={50} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Media search */}
        <section id="media" style={{ display: sectionVisible("media") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Media search</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {MEDIA_TOGGLES.map(({ key, label }) => (
              <label
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 12px",
                  background: form[key] ? "var(--accent-lt)" : "var(--sidebar)",
                  border: `1px solid ${form[key] ? "var(--accent)" : "var(--border)"}`,
                  borderRadius: "var(--radius)",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                <input
                  type="checkbox"
                  checked={form[key] as boolean}
                  onChange={(e) => set(key, e.target.checked as DomainConfigData[typeof key])}
                  style={{ accentColor: "var(--accent)" }}
                />
                {label}
              </label>
            ))}
          </div>
        </section>

        {/* Wytyczne redakcyjne */}
        <section id="wytyczne" style={{ display: sectionVisible("wytyczne") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Wytyczne redakcyjne</h3>
          <textarea
            value={form.guidelines}
            onChange={(e) => set("guidelines", e.target.value)}
            rows={12}
            placeholder="Markdown: zasady dotyczące tonu, struktury, SEO..."
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Format HTML */}
        <section id="html" style={{ display: sectionVisible("html") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Format HTML</h3>
          <textarea
            value={form.html_format}
            onChange={(e) => set("html_format", e.target.value)}
            rows={10}
            placeholder="Opis struktury HTML artykułu..."
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Stance recenzenta */}
        <section id="stance" style={{ display: sectionVisible("stance") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Stance recenzenta</h3>
          <textarea
            value={form.reflection_stance}
            onChange={(e) => set("reflection_stance", e.target.value)}
            rows={8}
            placeholder="Instrukcja dla agenta recenzenta..."
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Przykładowe artykuły */}
        <section id="przyklady" style={{ display: sectionVisible("przyklady") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Przykładowe artykuły</h3>
          {form.example_articles.map((text, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>Artykuł {i + 1}</span>
                <button
                  type="button"
                  onClick={() => set("example_articles", form.example_articles.filter((_, j) => j !== i))}
                  style={{ background: "none", border: "none", fontSize: 12, color: "#ef4444", cursor: "pointer" }}
                >
                  Usuń
                </button>
              </div>
              <textarea
                value={text}
                onChange={(e) => {
                  const updated = [...form.example_articles];
                  updated[i] = e.target.value;
                  set("example_articles", updated);
                }}
                rows={8}
                style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("example_articles", [...form.example_articles, ""])}
            style={{
              padding: "6px 14px",
              background: "none",
              border: "1px dashed var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 13,
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            + Dodaj artykuł
          </button>
        </section>
      </div>

      {/* Sticky save bar */}
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: "var(--sidebar-width)",
          right: 0,
          background: "var(--white)",
          borderTop: "1px solid var(--border)",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <button
          type="button"
          onClick={() => onSave(form)}
          disabled={saving}
          style={{
            padding: "8px 20px",
            background: saving ? "var(--border)" : "var(--accent)",
            color: saving ? "var(--muted)" : "var(--white)",
            border: "none",
            borderRadius: "var(--radius)",
            fontSize: 13,
            fontWeight: 500,
            cursor: saving ? "default" : "pointer",
          }}
        >
          {saving ? "Zapisywanie…" : "Zapisz zmiany"}
        </button>
        {error && <span style={{ fontSize: 12, color: "#ef4444" }}>{error}</span>}
        {!error && !saving && <span style={{ fontSize: 12, color: "var(--muted)" }}>Zmiany są widoczne od następnego uruchomienia pipeline'u</span>}
      </div>
    </div>
  );
}
