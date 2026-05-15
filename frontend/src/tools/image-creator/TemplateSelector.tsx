import type { ImageTemplate } from "../../types";
import { useT } from "../../i18n";

interface TemplateSelectorProps {
  templates: ImageTemplate[];
  onSelect: (template: ImageTemplate) => void;
}

export function TemplateSelector({ templates, onSelect }: TemplateSelectorProps) {
  const t = useT();

  if (templates.length === 0) {
    return (
      <p style={{ color: "var(--ink-subtle)", fontSize: 13, padding: "16px 0" }}>
        {t.imageCreator.noTemplates}
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ fontSize: 13, color: "var(--ink-subtle)", marginBottom: 4 }}>
        {t.imageCreator.selectTemplate}
      </p>
      {templates.map((tmpl) => (
        <button
          key={tmpl.id}
          onClick={() => onSelect(tmpl)}
          style={{
            padding: "10px 14px",
            textAlign: "left",
            background: "var(--card-bg)",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 500,
            color: "var(--ink)",
            fontFamily: "inherit",
            transition: "border-color .15s, background .15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.background = "var(--accent-lt)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--card-border)";
            e.currentTarget.style.background = "var(--card-bg)";
          }}
        >
          {tmpl.name || "(bez nazwy)"}
        </button>
      ))}
    </div>
  );
}
