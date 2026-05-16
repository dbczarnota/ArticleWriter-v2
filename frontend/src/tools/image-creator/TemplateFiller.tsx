import { useState, useMemo } from "react";
import type { ImageTemplate } from "../../types";
import type { ImageState } from "./htmlBuilder";
import { parsePlaceholders } from "./parsePlaceholders";
import { buildHtml } from "./htmlBuilder";
import { PlaceholderForm } from "./PlaceholderForm";
import { LivePreview } from "./LivePreview";
import { ImageMetaAccordion, EMPTY_META, type ImageMeta } from "./ImageMetaAccordion";

interface TemplateFillerProps {
  template: ImageTemplate;
  onSubmit: (html: string, meta: ImageMeta) => void;
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
  const [meta, setMeta] = useState<ImageMeta>(EMPTY_META);

  const placeholders = useMemo(() => parsePlaceholders(template.html), [template.html]);

  // Two HTML outputs:
  //   - previewHtml — pan/zoom stripped to defaults; passed to LivePreview's
  //     iframe srcDoc. Because the string is byte-identical across pan/zoom
  //     changes, React skips the srcDoc DOM update and the iframe doesn't
  //     reload (no flicker, no base64 re-decode). LivePreview re-applies the
  //     current pan/zoom imperatively after load.
  //   - filledHtml — full state baked in; used at submit time so htmltomedia
  //     receives the user's final crop and zoom.
  const previewHtml = useMemo(() => {
    const stable: Record<string, ImageState> = {};
    for (const [k, v] of Object.entries(imageStates)) {
      stable[k] = { dataUrl: v.dataUrl, panX: 0, panY: 0, scale: 1 };
    }
    return buildHtml(template.html, textValues, stable);
  }, [template.html, textValues, imageStates]);

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

  function handleImageRemove(label: string) {
    setImageStates((prev) => {
      const next = { ...prev };
      delete next[label];
      return next;
    });
    setActiveSlot((cur) => (cur === label ? null : cur));
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
    onSubmit(filledHtml, meta);
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
            onImageRemove={handleImageRemove}
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

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
        <LivePreview
          html={previewHtml}
          imageStates={imageStates}
          activeSlot={activeSlot}
          onActivateSlot={handleActivateSlot}
          onImageStateChange={handleImageStateChange}
        />
        <ImageMetaAccordion value={meta} onChange={setMeta} />
      </div>
    </div>
  );
}
