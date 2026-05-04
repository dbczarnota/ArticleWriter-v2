// frontend/src/components/DomainConfigForm.tsx
// TODO(tests): expand frontend test coverage to all components — NewArticleForm, ArticleView, SettingsView, Sidebar, CollapsibleSection
import { useEffect, useState } from "react";
import type { DomainConfigData } from "../types";

const MEDIA_TOGGLES: Array<{ key: keyof DomainConfigData; label: string; tip: string }> = [
  { key: "youtube_search", label: "YouTube", tip: "Szuka embeddowalnych filmów YouTube i Shorts powiązanych z tematem artykułu." },
  { key: "twitter_search", label: "Twitter/X", tip: "Szuka tweetów i postów X powiązanych z tematem — embeddowanie działa gdy URL jest publiczny." },
  { key: "tiktok_search", label: "TikTok", tip: "Szuka filmów TikTok powiązanych z tematem artykułu." },
  { key: "instagram_search", label: "Instagram", tip: "Szuka postów i Reelsów Instagram — wykrywane też ze scrapowanych stron konkurencji." },
  { key: "reddit_search", label: "Reddit", tip: "Szuka wątków Reddit — przydatne gdy temat ma duże zaangażowanie anglojęzyczne." },
  { key: "news_search", label: "News", tip: "Używa trybu wyszukiwania newsów Google zamiast zwykłego SERP — preferuje świeże artykuły prasowe." },
  { key: "facebook_search", label: "Facebook", tip: "Szuka publicznych postów i filmów Facebook. Embeddowanie wymaga publicznego URL." },
];

export const AVAILABLE_MODELS = [
  { id: "google-gla:gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  { id: "google-gla:gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { id: "anthropic:claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { id: "anthropic:claude-haiku-4-5", label: "Claude Haiku 4.5" },
  { id: "openai:gpt-4o", label: "GPT-4o" },
  { id: "openai:gpt-4o-mini", label: "GPT-4o Mini" },
];

const AGENT_DEFINITIONS: Array<{ key: string; label: string; tip: string }> = [
  { key: "search", label: "Wyszukiwanie", tip: "Formułuje zapytania Google i wybiera wyniki. Flash jest tu w porządku — to głównie logika zapytań, nie twórcze pisanie." },
  { key: "scraping", label: "Filtr scrapingu", tip: "Ocenia jakość scrapowanych stron i odrzuca te bez wartościowej treści. Lekki model wystarczy." },
  { key: "parsing", label: "Parsowanie", tip: "Klasyfikuje scrapowane strony (news, blog, konkurs...) i wyciąga metadane. Lekki krok — Flash wystarczy." },
  { key: "extraction", label: "Ekstrakcja", tip: "Wyciąga fakty i cytaty ze stron źródłowych. Jakość ekstrakcji wpływa bezpośrednio na jakość artykułu." },
  { key: "adaptive_search", label: "Adaptacyjne szukanie", tip: "Decyduje czy szukać dalej jeśli zebranych źródeł jest za mało. Uruchamia dodatkowe rundy wyszukiwania." },
  { key: "instructions", label: "Instrukcje", tip: "Analizuje zebrane źródła i tworzy szczegółowy brief dla pisarza. Pro — bo jakość briefa determinuje jakość artykułu." },
  { key: "writer", label: "Pisarz", tip: "Generuje gotowy artykuł HTML na podstawie briefa i źródeł. Najważniejszy agent — używaj najlepszego modelu." },
  { key: "reflection", label: "Recenzent", tip: "Sprawdza artykuł i zleca ewentualne poprawki pisarzowi. Może zrobić kilka rund." },
  { key: "followup", label: "Follow-up", tip: "Generuje alternatywne tytuły, tematy powiązane i śledzi które fakty/cytaty trafiły do artykułu. Pro bo wymaga kreatywności stylistycznej." },
];

const FRESHNESS_OPTIONS = [
  { value: "qdr:d", label: "Ostatni dzień" },
  { value: "qdr:w", label: "Ostatni tydzień" },
  { value: "qdr:m", label: "Ostatni miesiąc" },
  { value: "qdr:y", label: "Ostatni rok" },
];
const FIXED_FRESHNESS = new Set(FRESHNESS_OPTIONS.map((o) => o.value));

// Small tooltip icon — shows a floating box on hover.
function Tip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex", verticalAlign: "middle", marginLeft: 4 }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 14, height: 14, borderRadius: "50%",
        background: "var(--border)", color: "var(--muted)", fontSize: 9,
        cursor: "help", userSelect: "none", lineHeight: 1, flexShrink: 0,
      }}>?</span>
      {show && (
        <div style={{
          position: "absolute", left: 0, top: "calc(100% + 5px)",
          background: "#1e293b", color: "#f1f5f9", fontSize: 11,
          borderRadius: 5, padding: "7px 10px", width: 260,
          zIndex: 1000, lineHeight: 1.55, pointerEvents: "none",
          boxShadow: "0 4px 16px rgba(0,0,0,.25)",
          whiteSpace: "normal",
        }}>
          {text}
        </div>
      )}
    </span>
  );
}

interface DomainConfigFormProps {
  initialConfig: DomainConfigData;
  activeSection: string;
  saving: boolean;
  error: string | null;
  onSave: (config: DomainConfigData) => void;
}

export function DomainConfigForm({ initialConfig, activeSection, saving, error, onSave }: DomainConfigFormProps) {
  const [form, setForm] = useState<DomainConfigData>(initialConfig);

  useEffect(() => {
    setForm(initialConfig);
  }, [initialConfig]);

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
    display: "flex",
    alignItems: "center",
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
              <label style={labelStyle}>
                Opis domeny
                <Tip text="Krótki opis redakcji przekazywany agentom jako kontekst. Pomaga modelom zrozumieć styl i temat portalu. Np. 'Polski portal lifestyle, krótkie clickbaitowe artykuły'." />
              </label>
              <textarea value={form.description} onChange={(e) => set("description", e.target.value)} rows={3} style={{ ...inputStyle, resize: "vertical" }} />
            </div>
            <div>
              <label style={labelStyle}>
                Język artykułów
                <Tip text="Kod języka wg ISO 639-1 (np. 'pl', 'en'). Artykuły są generowane w tym języku." />
              </label>
              <input value={form.language} onChange={(e) => set("language", e.target.value)} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Wyszukiwanie */}
        <section id="wyszukiwanie" style={{ display: sectionVisible("wyszukiwanie") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Wyszukiwanie</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>
                Docelowa długość (słów)
                <Tip text="Przybliżona liczba słów gotowego artykułu. Agent pisarz stara się trafić w tę wartość — nie jest to twardy limit." />
              </label>
              <input type="number" value={form.target_word_count} onChange={(e) => set("target_word_count", +e.target.value)} min={100} max={5000} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Świeżość wyników
                <Tip text="Ogranicza wyniki Google do wybranego okresu. 'Ostatni dzień' = gorące newsy; 'Ostatni rok' = szerszy kontekst tematyczny. Domyślnie: tydzień." />
              </label>
              {(() => {
                const isCustom = !FIXED_FRESHNESS.has(form.search_freshness);
                const customDays = isCustom ? (parseInt(form.search_freshness.replace("qdr:", "")) || 7) : 7;
                return (
                  <>
                    <select
                      value={isCustom ? "__custom__" : form.search_freshness}
                      onChange={(e) => set("search_freshness", e.target.value === "__custom__" ? `qdr:${customDays}` : e.target.value)}
                      style={inputStyle}
                    >
                      {FRESHNESS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      <option value="__custom__">Własna (wpisz dni)</option>
                    </select>
                    {isCustom && (
                      <input
                        type="number"
                        value={customDays}
                        min={1}
                        max={365}
                        onChange={(e) => set("search_freshness", `qdr:${Math.max(1, +e.target.value)}`)}
                        style={{ ...inputStyle, marginTop: 6 }}
                        placeholder="Liczba dni"
                      />
                    )}
                  </>
                );
              })()}
            </div>
            <div>
              <label style={labelStyle}>
                Liczba zapytań
                <Tip text="Ile różnych zapytań Google wysyła agent wyszukiwarki równolegle. Więcej = szersza wiedza, dłuższy czas wykonania." />
              </label>
              <input type="number" value={form.num_queries} onChange={(e) => set("num_queries", +e.target.value)} min={1} max={10} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Max wyników / zapytanie
                <Tip text="Ile wyników SERP bierze pod uwagę każde zapytanie. Bezpośrednio wpływa na liczbę stron do scrapowania." />
              </label>
              <input type="number" value={form.max_results} onChange={(e) => set("max_results", +e.target.value)} min={1} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Min sygnałów źródłowych
                <Tip text="Minimalna łączna liczba faktów + cytatów wymagana do generowania artykułu. Jeśli pipeline zbierze mniej — zwraca błąd 'insufficient_sources' zamiast pisać słaby artykuł." />
              </label>
              <input type="number" value={form.min_source_signals} onChange={(e) => set("min_source_signals", +e.target.value)} min={0} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Max stron do scrapowania
                <Tip text="Ile artykułów źródłowych pipeline faktycznie pobiera i czyta. Więcej = lepsza jakość materiałów, ale wolniej i drożej." />
              </label>
              <input type="number" value={form.max_pages_to_scrape} onChange={(e) => set("max_pages_to_scrape", +e.target.value)} min={1} max={50} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Max faktów w artykule
                <Tip text="Ile faktów agent ekstrakcji może przekazać pisarzowi ze wszystkich źródeł łącznie. Pisarz wybiera z nich co uwzględnić w tekście." />
              </label>
              <input type="number" value={form.max_facts} onChange={(e) => set("max_facts", +e.target.value)} min={1} max={50} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Max cytatów w artykule
                <Tip text="Ile cytatów (dosłownych wypowiedzi osób) trafia do kontekstu pisarza. Dobre cytaty wzmacniają autentyczność artykułu." />
              </label>
              <input type="number" value={form.max_quotes} onChange={(e) => set("max_quotes", +e.target.value)} min={0} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Artykuły kontekstowe (refleksja)
                <Tip text="Ile artykułów konkurencji (ze scrapowanych stron) dostaje agent-recenzent jako kontekst. Pomaga mu ocenić, czy nasz artykuł wnosi coś nowego i nie powtarza oczywistości." />
              </label>
              <input type="number" value={form.reflection_context_articles} onChange={(e) => set("reflection_context_articles", +e.target.value)} min={0} max={10} style={inputStyle} />
            </div>
          </div>
        </section>

        {/* Media search */}
        <section id="media" style={{ display: sectionVisible("media") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
            Media search
            <Tip text="Pipeline szuka embeddowalnych postów z wybranych platform i próbuje umieścić je w artykule jako enrichment." />
          </h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>Zaznacz platformy, z których pipeline ma szukać embeddowalnych mediów.</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {MEDIA_TOGGLES.map(({ key, label, tip }) => (
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
                <Tip text={tip} />
              </label>
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
            <div>
              <label style={labelStyle}>
                Języki media search (po przecinku)
                <Tip text="Języki używane przy wyszukiwaniu mediów społecznościowych. 'en, pl' = szuka po angielsku i polsku. Wpływa na dopasowanie kulturowe wyników." />
              </label>
              <input
                value={form.media_search_languages.join(", ")}
                onChange={(e) => set("media_search_languages", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
                placeholder="en, pl"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>
                Liczba wyników media search
                <Tip text="Ile wyników zwraca jedno zapytanie o media społecznościowe. Więcej = większy wybór embeddów, ale wolniej." />
              </label>
              <input type="number" value={form.media_search_num} onChange={(e) => set("media_search_num", +e.target.value)} min={1} max={20} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>
                Max tiers zapytań media
                <Tip text="Głębokość wyszukiwania embeddowalnych mediów. Tier 2 = dodatkowe zapytania-wariacje jeśli tier 1 zwróci mało wyników. Wyższe wartości = więcej tokenów." />
              </label>
              <input type="number" value={form.media_search_max_query_tiers} onChange={(e) => set("media_search_max_query_tiers", +e.target.value)} min={1} max={5} style={inputStyle} />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer", paddingTop: 20 }}>
              <input
                type="checkbox"
                checked={form.youtube_sort_by_date}
                onChange={(e) => set("youtube_sort_by_date", e.target.checked)}
                style={{ accentColor: "var(--accent)" }}
              />
              Sortuj YouTube po dacie
              <Tip text="Sortuje wyniki YouTube od najnowszych zamiast 'relevance'. Zalecane dla newsów — gwarantuje świeże materiały powiązane z aktualnym tematem." />
            </label>
          </div>
        </section>

        {/* Wybór modeli */}
        <section id="modele" style={{ display: sectionVisible("modele") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>Wybór modeli</h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
            Domyślne modele dla każdego agenta. Można nadpisać per-artykuł w opcjach zaawansowanych.
            Puste = hardcoded domyślny (Flash dla lekkich kroków, Pro dla pisania i instrukcji). Fallbacki oddzielone przecinkiem.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {AGENT_DEFINITIONS.map(({ key, label, tip }) => (
              <div key={key} style={{ display: "grid", gridTemplateColumns: "200px 1fr 1fr", gap: 8, alignItems: "center" }}>
                <label style={{ ...labelStyle, marginBottom: 0 }}>
                  {label}
                  <Tip text={tip} />
                </label>
                <select
                  value={form.agent_models[key] ?? ""}
                  onChange={(e) => set("agent_models", { ...form.agent_models, [key]: e.target.value })}
                  style={inputStyle}
                >
                  <option value="">— domyślny —</option>
                  {AVAILABLE_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
                <div style={{ position: "relative" }}>
                  <input
                    value={(form.agent_fallback_models[key] ?? []).join(", ")}
                    onChange={(e) => {
                      const vals = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                      set("agent_fallback_models", { ...form.agent_fallback_models, [key]: vals });
                    }}
                    placeholder="Fallbacki (opcjonalne)"
                    style={{ ...inputStyle, fontSize: 12, fontFamily: "monospace" }}
                  />
                  <span style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)" }}>
                    <Tip text="Modele awaryjne oddzielone przecinkiem (np. 'groq:openai/gpt-oss-120b'). Używane gdy główny model zwróci błąd, timeout lub przekroczy limit." />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Wytyczne redakcyjne */}
        <section id="wytyczne" style={{ display: sectionVisible("wytyczne") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            Wytyczne redakcyjne
            <Tip text="Pełna 'Biblia Redaktora' w formacie Markdown. Przekazywana agentowi instrukcji i pisarzowi. Definiuj ton głosu, strukturę artykułu, zasady SEO, czego unikać, jakich słów używać, jak tytułować." />
          </h3>
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
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            Format HTML
            <Tip text="Szablon lub opis oczekiwanej struktury HTML artykułu. Agent pisarz stosuje ten format generując kod. Można wkleić przykładowy artykuł z placeholderami albo opisać strukturę tagami." />
          </h3>
          <textarea
            value={form.html_format}
            onChange={(e) => set("html_format", e.target.value)}
            rows={10}
            placeholder="Opis struktury HTML artykułu..."
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Recenzent */}
        <section id="stance" style={{ display: sectionVisible("stance") ? "block" : "none", marginBottom: 32 }}>
          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>
              Liczba rund recenzji
              <Tip text="Ile razy pętla recenzent→pisarz może się powtórzyć. 1 = jedna recenzja i jedna poprawka (domyślnie). 2–3 = głębsza iteracja, ale dłuższy czas i większy koszt." />
            </label>
            <input
              type="number"
              value={form.reflection_rounds}
              onChange={(e) => set("reflection_rounds", Math.max(1, Math.min(5, +e.target.value)))}
              min={1}
              max={5}
              style={{ ...inputStyle, width: 80 }}
            />
          </div>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            Dodatkowe instrukcje dla recenzenta
            <Tip text="Opcjonalne wskazówki dla agenta recenzenta (QA) wykraczające poza jego wbudowane reguły. Zostaw puste jeśli domyślne zachowanie recenzenta jest wystarczające." />
          </h3>
          <textarea
            value={form.reflection_stance}
            onChange={(e) => set("reflection_stance", e.target.value)}
            rows={6}
            placeholder="Zostaw puste — recenzent ma wbudowane reguły jakości. Wpisz tylko jeśli chcesz dodać coś specyficznego dla tej domeny."
            style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
          />
        </section>

        {/* Przykładowe H1 */}
        <section id="tytuly" style={{ display: sectionVisible("tytuly") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
            Przykładowe H1
            <Tip text="Wzorcowe tytuły artykułów Twojej redakcji. Agent follow-up generuje alternatywne tytuły naśladując dokładnie ten styl — długość, emocje, użycie wielkich liter, strukturę zdania." />
          </h3>
          <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>
            Im więcej przykładów, tym trafniejszy styl alternatywnych tytułów.
          </p>
          {form.example_titles.map((text, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
              <input
                value={text}
                onChange={(e) => {
                  const updated = [...form.example_titles];
                  updated[i] = e.target.value;
                  set("example_titles", updated);
                }}
                placeholder={`Tytuł ${i + 1}`}
                style={{ ...inputStyle, flex: 1 }}
              />
              <button
                type="button"
                onClick={() => set("example_titles", form.example_titles.filter((_, j) => j !== i))}
                style={{ background: "none", border: "none", fontSize: 13, color: "#ef4444", cursor: "pointer", flexShrink: 0 }}
              >
                Usuń
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => set("example_titles", [...form.example_titles, ""])}
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
            + Dodaj tytuł
          </button>
        </section>

        {/* Przykładowe artykuły */}
        <section id="przyklady" style={{ display: sectionVisible("przyklady") ? "block" : "none", marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            Przykładowe artykuły
            <Tip text="Pełne artykuły jako 'few-shot examples'. Agent instrukcji analizuje je tworząc brief dla pisarza. Im lepszy przykład, tym dokładniej pipeline odwzorowuje styl i strukturę redakcji." />
          </h3>
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
