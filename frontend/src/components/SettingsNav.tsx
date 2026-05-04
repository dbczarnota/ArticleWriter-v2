// frontend/src/components/SettingsNav.tsx
const SECTIONS = [
  { id: "podstawowe", label: "Podstawowe" },
  { id: "modele", label: "Wybór modeli" },
  { id: "wyszukiwanie", label: "Wyszukiwanie" },
  { id: "media", label: "Media search" },
  { id: "wytyczne", label: "Wytyczne redakcyjne" },
  { id: "html", label: "Format HTML" },
  { id: "stance", label: "Recenzent" },
  { id: "tytuly", label: "Przykładowe H1" },
  { id: "przyklady", label: "Przykładowe artykuły" },
];

interface SettingsNavProps {
  activeSection: string;
  onSelect: (id: string) => void;
}

export function SettingsNav({ activeSection, onSelect }: SettingsNavProps) {
  return (
    <nav style={{ width: 200, flexShrink: 0 }}>
      {SECTIONS.map((s) => (
        <button
          key={s.id}
          onClick={() => onSelect(s.id)}
          style={{
            display: "block",
            width: "100%",
            padding: "8px 12px",
            textAlign: "left",
            background: activeSection === s.id ? "var(--accent-lt)" : "none",
            borderLeft: activeSection === s.id ? "3px solid var(--accent)" : "3px solid transparent",
            borderTop: "none",
            borderRight: "none",
            borderBottom: "none",
            fontSize: 13,
            fontWeight: activeSection === s.id ? 500 : 400,
            color: activeSection === s.id ? "var(--accent)" : "var(--text)",
            cursor: "pointer",
            borderRadius: "0 var(--radius) var(--radius) 0",
          }}
        >
          {s.label}
        </button>
      ))}
    </nav>
  );
}
