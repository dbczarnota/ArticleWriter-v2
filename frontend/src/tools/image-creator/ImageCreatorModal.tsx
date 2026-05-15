import { useState } from "react";
import type { ImageTemplate } from "../../types";
import { useImageTemplates } from "./useImageTemplates";
import { useImageCreatorJob } from "./useImageCreatorJob";
import { TemplateSelector } from "./TemplateSelector";
import { TemplateFiller } from "./TemplateFiller";
import { ResultPanel } from "./ResultPanel";
import { useT } from "../../i18n";

type Step = "template" | "filling" | "result";

interface ImageCreatorModalProps {
  onClose: () => void;
  articleId?: string | null;
  articleSelector?: React.ReactNode;
}

export function ImageCreatorModal({
  onClose,
  articleId,
  articleSelector,
}: ImageCreatorModalProps) {
  const t = useT();
  const templates = useImageTemplates();
  const { status, result, submit, reset } = useImageCreatorJob();

  const [step, setStep] = useState<Step>("template");
  const [selectedTemplate, setSelectedTemplate] = useState<ImageTemplate | null>(null);

  function handleSelectTemplate(template: ImageTemplate) {
    setSelectedTemplate(template);
    setStep("filling");
  }

  function handleBackToTemplate() {
    setSelectedTemplate(null);
    setStep("template");
  }

  async function handleSubmitFilled(html: string) {
    await submit(html, articleId ?? null, selectedTemplate?.name ?? "");
    setStep("result");
  }

  function handleDownload() {
    if (result.url) {
      const ext = result.url.match(/\.(png|jpe?g|webp|gif)(?:\?|$)/i)?.[1] ?? "png";
      const link = document.createElement("a");
      link.href = result.url;
      link.download = `image-${Date.now()}.${ext.toLowerCase()}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }

  function handleClose() {
    reset();
    onClose();
  }

  const headerTitle =
    step === "template" ? t.imageCreator.modalTitle :
    step === "filling" ? (selectedTemplate?.name ?? t.imageCreator.modalTitle) :
    t.imageCreator.resultTitle;

  return (
    <>
      <header
        style={{
          padding: "14px 18px",
          borderBottom: "1px solid var(--card-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          {step === "filling" && (
            <button
              onClick={handleBackToTemplate}
              style={{
                padding: "4px 8px",
                background: "transparent",
                border: "1px solid var(--card-border)",
                borderRadius: "var(--radius)",
                fontSize: 12,
                color: "var(--ink-subtle)",
                cursor: "pointer",
                fontFamily: "inherit",
                flexShrink: 0,
              }}
            >
              ← {t.imageCreator.backToTemplate}
            </button>
          )}
          <h3 style={{ margin: 0, fontSize: 16, color: "var(--ink)", fontWeight: 800, letterSpacing: "-.025em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {headerTitle}
          </h3>
        </div>
        <button
          onClick={handleClose}
          aria-label={t.imageCreator.close}
          style={{
            width: 28,
            height: 28,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            background: "transparent",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            cursor: "pointer",
            color: "var(--ink-subtle)",
            fontFamily: "inherit",
            fontSize: 14,
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </header>

      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {step === "template" && (
          <div style={{ padding: "20px 24px", overflowY: "auto" }}>
            <TemplateSelector templates={templates} onSelect={handleSelectTemplate} />
          </div>
        )}

        {step === "filling" && selectedTemplate && (
          <TemplateFiller
            template={selectedTemplate}
            articleSelector={articleSelector}
            onSubmit={handleSubmitFilled}
            submitLabel={
              status === "submitting" || status === "waiting"
                ? t.imageCreator.generatingImage
                : t.imageCreator.generateImage
            }
            isSubmitting={status === "submitting" || status === "waiting"}
          />
        )}

        {step === "result" && result.url && (
          <ResultPanel
            url={result.url}
            onClose={handleClose}
            onDownload={handleDownload}
          />
        )}

        {step === "result" && result.error && (
          <div style={{ padding: "24px", textAlign: "center" }}>
            <p style={{ color: "var(--error)", marginBottom: 16, fontSize: 13 }}>
              {result.error}
            </p>
            <button
              onClick={handleBackToTemplate}
              style={{
                padding: "8px 16px",
                background: "var(--accent)",
                color: "white",
                border: "none",
                borderRadius: "var(--radius)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              {t.imageCreator.tryAgain}
            </button>
          </div>
        )}
      </div>
    </>
  );
}
