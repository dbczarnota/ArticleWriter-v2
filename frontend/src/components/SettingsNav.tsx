import { useT } from "../i18n";

const SECTION_IDS = ["podstawowe", "modele", "wyszukiwanie", "media", "wytyczne", "html", "stance", "tytuly", "przyklady", "szablony", "szablony-obrazkow", "discovery", "streamy", "integracje"] as const;
type SectionId = typeof SECTION_IDS[number];

interface SettingsNavProps {
  activeSection: string;
  onSelect: (id: string) => void;
}

export function SettingsNav({ activeSection, onSelect }: SettingsNavProps) {
  const t = useT();

  const labels: Record<SectionId, string> = {
    podstawowe: t.settingsNav.basic,
    modele: t.settingsNav.models,
    wyszukiwanie: t.settingsNav.search,
    media: t.settingsNav.mediaSearch,
    wytyczne: t.settingsNav.guidelines,
    html: t.settingsNav.htmlFormat,
    stance: t.settingsNav.reviewer,
    tytuly: t.settingsNav.exampleTitles,
    przyklady: t.settingsNav.exampleArticles,
    szablony: t.settingsNav.templates,
    "szablony-obrazkow": t.settingsNav.imageTemplates,
    discovery: t.settingsNav.discovery,
    streamy: t.settingsNav.streams,
    integracje: t.settingsNav.integrations,
  };

  return (
    <nav style={{ width: 200, flexShrink: 0 }}>
      {SECTION_IDS.map((id) => (
        <button
          key={id}
          onClick={() => onSelect(id)}
          style={{
            display: "block",
            width: "100%",
            padding: "8px 12px",
            textAlign: "left",
            background: activeSection === id ? "var(--accent-lt)" : "none",
            borderLeft: activeSection === id ? "3px solid var(--accent)" : "3px solid transparent",
            borderTop: "none",
            borderRight: "none",
            borderBottom: "none",
            fontSize: 13,
            fontWeight: activeSection === id ? 500 : 400,
            color: activeSection === id ? "var(--accent)" : "var(--text)",
            cursor: "pointer",
            borderRadius: "0 var(--radius) var(--radius) 0",
          }}
        >
          {labels[id]}
        </button>
      ))}
    </nav>
  );
}
