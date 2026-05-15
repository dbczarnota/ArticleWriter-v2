import { useState } from "react";
import type { ImageTemplate, ArticleListItem } from "../../types";
import { useImageTemplates } from "./useImageTemplates";
import { useImageCreatorJob } from "./useImageCreatorJob";
import { TemplateSelector } from "./TemplateSelector";
import { TemplateFiller } from "./TemplateFiller";
import { ResultPanel } from "./ResultPanel";
import { useT } from "../../i18n";

type Step = "template" | "filling" | "result";

interface ImageCreatorModalProps {
  onClose: () => void;
  currentArticle: ArticleListItem | null;
}

export function ImageCreatorModal({
  onClose,
  currentArticle,
}: ImageCreatorModalProps) {
  const t = useT();
  const templates = useImageTemplates();
  const { status, result, submit, reset } = useImageCreatorJob();

  const [step, setStep] = useState<Step>("template");
  const [selectedTemplate, setSelectedTemplate] = useState<ImageTemplate | null>(null);
  const [attachToArticle, setAttachToArticle] = useState<boolean>(!!currentArticle);

  function handleSelectTemplate(template: ImageTemplate) {
    setSelectedTemplate(template);
    setStep("filling");
  }

  function handleBackToTemplate() {
    setSelectedTemplate(null);
    setStep("template");
  }

  async function handleSubmitFilled(html: string) {
    const articleId = attachToArticle && currentArticle ? currentArticle.id : null;
    await submit(html, articleId, selectedTemplate?.name ?? "");
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

  const articleSelector = currentArticle ? (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--ink-subtle)" }}>
        {t.imageCreator.assignToArticle}
      </label>
      <label style={{ display: "flex", alignItems: "flex-start", gap: 8, cursor: "pointer", padding: "8px 10px", border: `1px solid ${attachToArticle ? "var(--accent)" : "var(--card-border)"}`, background: attachToArticle ? "var(--accent-lt)" : "var(--card-bg)", borderRadius: "var(--radius)", transition: "border-color .15s, background .15s" }}>
        <input
          type="checkbox"
          checked={attachToArticle}
          onChange={(e) => setAttachToArticle(e.target.checked)}
          style={{ marginTop: 2, flexShrink: 0, accentColor: "var(--accent)" }}
        />
        <span style={{ fontSize: 12, color: "var(--ink)", lineHeight: 1.35, wordBreak: "break-word" }}>
          {currentArticle.topic}
        </span>
      </label>
      {!attachToArticle && (
        <span style={{ fontSize: 10, color: "var(--ink-subtle)" }}>
          {t.imageCreator.noArticle}
        </span>
      )}
    </div>
  ) : (
    <div style={{ fontSize: 11, color: "var(--ink-subtle)", fontStyle: "italic", padding: "6px 0" }}>
      {t.imageCreator.noArticle}
    </div>
  );

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
