import { useState, useMemo } from "react";
import type { ImageTemplate } from "../../types";
import type { ImageState } from "./htmlBuilder";
import { parsePlaceholders } from "./parsePlaceholders";
import { buildHtml } from "./htmlBuilder";
import { PlaceholderForm } from "./PlaceholderForm";
import { LivePreview } from "./LivePreview";

interface TemplateFillerProps {
  template: ImageTemplate;
  onSubmit: (html: string) => void;
  articleSelector?: React.ReactNode;
  submitLabel: string;
  isSubmitting: boolean;
}

export function TemplateFiller({
  template,
  onSubmit,
  articleSelector,
  submitLabel,
  isSubmitting,
}: TemplateFillerProps) {
  const [textValues, setTextValues] = useState<Record<string, string>>({});
  const [imageStates, setImageStates] = useState<Record<string, ImageState>>({});
  const [activeSlot, setActiveSlot] = useState<string | null>(null);

  const placeholders = useMemo(() => parsePlaceholders(template.html), [template.html]);

  const filledHtml = useMemo(
    () => buildHtml(template.html, textValues, imageStates),
    [template.html, textValues, imageStates]
  );

  function handleTextChange(label: string, value: string) {
    setTextValues((prev) => ({ ...prev, [label]: value }));
  }

  function handleImageUpload(label: string, state: ImageState) {
    setImageStates((prev) => ({ ...prev, [label]: state }));
  }

  function handleActivateSlot(label: string) {
    setActiveSlot(label);
  }

  function handleImageStateChange(label: string, state: Partial<ImageState>) {
    setImageStates((prev) => ({
      ...prev,
      [label]: { ...prev[label]!, ...state },
    }));
  }

  function handleSubmit() {
    onSubmit(filledHtml);
  }

  return (
    <div style={{ display: "flex", gap: 0, height: "100%", minHeight: 0 }}>
      <div style={{ width: 300, display: "flex", flexDirection: "column", borderRight: "1px solid var(--card-border)", background: "var(--card-bg)" }}>
        <div style={{ flex: 1, overflowY: "auto" }}>
          <PlaceholderForm
            placeholders={placeholders}
            textValues={textValues}
            imageStates={imageStates}
            activeSlot={activeSlot}
            onTextChange={handleTextChange}
            onImageUpload={handleImageUpload}
            onActivateSlot={handleActivateSlot}
          />
        </div>

        {articleSelector && (
          <div style={{ padding: "12px 14px", borderTop: "1px solid var(--card-border)" }}>
            {articleSelector}
          </div>
        )}

        <div style={{ padding: "12px 14px", borderTop: "1px solid var(--border)" }}>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            style={{
              width: "100%",
              padding: "8px 12px",
              background: "var(--accent)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius)",
              fontSize: 12,
              fontWeight: 600,
              cursor: isSubmitting ? "not-allowed" : "pointer",
              opacity: isSubmitting ? 0.6 : 1,
              fontFamily: "inherit",
            }}
          >
            {submitLabel}
          </button>
        </div>
      </div>

      <LivePreview
        html={filledHtml}
        activeSlot={activeSlot}
        onImageStateChange={handleImageStateChange}
      />
    </div>
  );
}
