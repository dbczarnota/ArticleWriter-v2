import { useRef } from "react";
import type { Placeholder } from "./parsePlaceholders";
import type { ImageState } from "./htmlBuilder";
import { prepareImage } from "./imagePrepare";
import { useT } from "../../i18n";

interface PlaceholderFormProps {
  placeholders: Placeholder[];
  textValues: Record<string, string>;
  imageStates: Record<string, ImageState>;
  activeSlot: string | null;
  onTextChange: (label: string, value: string) => void;
  onImageUpload: (label: string, state: ImageState) => void;
  onActivateSlot: (label: string) => void;
}

export function PlaceholderForm({
  placeholders,
  textValues,
  imageStates,
  activeSlot,
  onTextChange,
  onImageUpload,
  onActivateSlot,
}: PlaceholderFormProps) {
  const t = useT();
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  async function handleFile(label: string, file: File) {
    const dataUrl = await prepareImage(file);
    onImageUpload(label, { dataUrl, posX: 50, posY: 50, scale: 1 });
    onActivateSlot(label);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "12px 14px", overflowY: "auto" }}>
      {placeholders.map((ph) => (
        <div key={`${ph.type}:${ph.label}`}>
          <label style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--muted)", display: "block", marginBottom: 4 }}>
            {ph.type === "TEXT" ? "🔤" : "🖼"} {ph.label}
          </label>
          {ph.type === "TEXT" ? (
            <input
              value={textValues[ph.label] ?? ""}
              onChange={(e) => onTextChange(ph.label, e.target.value)}
              placeholder={t.imageCreator.textPlaceholder}
              style={{ width: "100%", padding: "6px 8px", border: "1px solid var(--border)", borderRadius: "var(--radius)", fontSize: 12, fontFamily: "inherit", boxSizing: "border-box" }}
            />
          ) : (
            <div
              onClick={() => {
                if (imageStates[ph.label]?.dataUrl) {
                  onActivateSlot(ph.label);
                } else {
                  fileInputRefs.current[ph.label]?.click();
                }
              }}
              style={{
                border: `1.5px ${activeSlot === ph.label ? "solid var(--accent)" : "dashed var(--border)"}`,
                borderRadius: "var(--radius)",
                padding: 8,
                cursor: "pointer",
                background: activeSlot === ph.label ? "var(--accent-lt)" : "var(--chrome-bg2)",
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "var(--muted)",
              }}
            >
              {imageStates[ph.label]?.dataUrl ? (
                <>
                  <img
                    src={imageStates[ph.label].dataUrl!}
                    alt=""
                    style={{ width: 40, height: 28, objectFit: "cover", borderRadius: 3, flexShrink: 0 }}
                  />
                  <span style={{ color: "var(--accent)", fontWeight: 500 }}>
                    {activeSlot === ph.label ? "↔ Przeciągnij na podglądzie" : "Kliknij by kadrować"}
                  </span>
                </>
              ) : (
                <span>📁 {t.imageCreator.uploadImage}</span>
              )}
            </div>
          )}
          <input
            ref={(el) => { fileInputRefs.current[ph.label] = el; }}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(ph.label, file);
              e.target.value = "";
            }}
          />
        </div>
      ))}
    </div>
  );
}
