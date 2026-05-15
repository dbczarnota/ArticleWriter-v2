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
      const link = document.createElement("a");
      link.href = result.url;
      link.download = `image-${Date.now()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      {step === "template" && (
        <div style={{ padding: "16px 24px" }}>
          <h2 style={{ margin: "0 0 16px 0", fontSize: 16, fontWeight: 600 }}>
            {t.imageCreator.selectTemplate}
          </h2>
          <TemplateSelector templates={templates} onSelect={handleSelectTemplate} />
        </div>
      )}

      {step === "filling" && selectedTemplate && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            flex: 1,
            minHeight: 0,
          }}
        >
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <button
              onClick={handleBackToTemplate}
              style={{
                padding: 0,
                background: "none",
                border: "none",
                cursor: "pointer",
                fontSize: 12,
                color: "var(--accent)",
                fontWeight: 500,
                fontFamily: "inherit",
              }}
            >
              ← {t.imageCreator.backToTemplate}
            </button>
            <span style={{ fontSize: 12, fontWeight: 600 }}>
              {selectedTemplate.name}
            </span>
          </div>
          <div style={{ flex: 1, minHeight: 0 }}>
            <TemplateFiller
              template={selectedTemplate}
              articleSelector={articleSelector}
              onSubmit={handleSubmitFilled}
              submitLabel={
                status === "submitting"
                  ? t.imageCreator.generatingImage
                  : t.imageCreator.generateImage
              }
              isSubmitting={status === "submitting" || status === "waiting"}
            />
          </div>
        </div>
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

      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--border)",
          textAlign: "right",
        }}
      >
        <button
          onClick={handleClose}
          style={{
            padding: "6px 12px",
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {t.imageCreator.close}
        </button>
      </div>
    </div>
  );
}
