import { useState } from "react";
import { useT } from "../../i18n";

export interface ImageMeta {
  filename: string;
  caption: string;
  description: string;
  alt: string;
}

export const EMPTY_META: ImageMeta = { filename: "", caption: "", description: "", alt: "" };

interface ImageMetaAccordionProps {
  value: ImageMeta;
  onChange: (next: ImageMeta) => void;
}

export function ImageMetaAccordion({ value, onChange }: ImageMetaAccordionProps) {
  const t = useT();
  const [open, setOpen] = useState(false);

  const filledCount = [value.filename, value.caption, value.description, value.alt].filter(
    (v) => v.trim() !== "",
  ).length;

  function set<K extends keyof ImageMeta>(key: K, v: string) {
    onChange({ ...value, [key]: v });
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: ".06em",
    color: "var(--ink-subtle)",
    marginBottom: 4,
    display: "block",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "6px 8px",
    border: "1px solid var(--card-border)",
    borderRadius: "var(--radius)",
    fontSize: 12,
    fontFamily: "inherit",
    boxSizing: "border-box",
    background: "var(--card-bg)",
    color: "var(--ink)",
  };

  return (
    <div style={{ borderTop: "1px solid var(--card-border)", background: "var(--card-bg)" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          fontSize: 12,
          fontWeight: 600,
          color: "var(--ink)",
          fontFamily: "inherit",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span style={{ transition: "transform .15s", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>▸</span>
          {t.imageCreator.advanced}
          {filledCount > 0 && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                background: "var(--accent-lt)",
                color: "var(--accent)",
                padding: "1px 6px",
                borderRadius: 999,
              }}
            >
              {filledCount}
            </span>
          )}
        </span>
      </button>
      {open && (
        <div style={{ padding: "4px 14px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
          <p style={{ margin: 0, fontSize: 11, color: "var(--ink-subtle)" }}>{t.imageCreator.metaOptional}</p>
          <div>
            <label style={labelStyle}>{t.imageCreator.metaFilename}</label>
            <input
              value={value.filename}
              onChange={(e) => set("filename", e.target.value)}
              placeholder="moj-obraz"
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>{t.imageCreator.metaCaption}</label>
            <input value={value.caption} onChange={(e) => set("caption", e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>{t.imageCreator.metaAlt}</label>
            <input value={value.alt} onChange={(e) => set("alt", e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>{t.imageCreator.metaDescription}</label>
            <textarea
              value={value.description}
              onChange={(e) => set("description", e.target.value)}
              rows={3}
              style={{ ...inputStyle, resize: "vertical", minHeight: 56 }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
