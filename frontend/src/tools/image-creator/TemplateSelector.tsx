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
      <p style={{ color: "var(--muted)", fontSize: 13, padding: "16px 0" }}>
        {t.imageCreator.noTemplates}
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 4 }}>
        {t.imageCreator.selectTemplate}
      </p>
      {templates.map((tmpl) => (
        <button
          key={tmpl.id}
          onClick={() => onSelect(tmpl)}
          style={{
            padding: "10px 14px",
            textAlign: "left",
            background: "var(--chrome-bg2)",
            border: "1px solid var(--chrome-border)",
            borderRadius: "var(--radius)",
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 500,
            color: "var(--chrome-ink)",
            fontFamily: "inherit",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--chrome-border)"; }}
        >
          {tmpl.name || "(bez nazwy)"}
        </button>
      ))}
    </div>
  );
}
