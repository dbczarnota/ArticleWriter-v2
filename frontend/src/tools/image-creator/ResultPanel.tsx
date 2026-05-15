import { useState } from "react";
import { useT } from "../../i18n";

interface ResultPanelProps {
  url: string;
  onClose: () => void;
  onDownload?: () => void;
}

export function ResultPanel({ url, onClose, onDownload }: ResultPanelProps) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard may be unavailable in some embeds; ignore
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: "auto",
          padding: "24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--canvas-bg)",
        }}
      >
        <img
          src={url}
          alt="Generated"
          style={{
            maxWidth: "100%",
            maxHeight: "100%",
            objectFit: "contain",
            borderRadius: "var(--radius)",
            border: "1px solid var(--card-border)",
            boxShadow: "0 4px 16px rgba(0,0,0,.08)",
          }}
        />
      </div>

      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid var(--card-border)",
          display: "flex",
          gap: 8,
          alignItems: "center",
          background: "var(--card-bg)",
          flexShrink: 0,
        }}
      >
        <input
          type="text"
          value={url}
          readOnly
          onFocus={(e) => e.currentTarget.select()}
          style={{
            flex: 1,
            minWidth: 0,
            padding: "6px 10px",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            background: "var(--canvas-bg)",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
            color: "var(--ink-subtle)",
            boxSizing: "border-box",
          }}
        />
        <button
          onClick={handleCopyLink}
          style={{
            padding: "6px 12px",
            background: copied ? "var(--success, #16a34a)" : "var(--card-bg)",
            color: copied ? "white" : "var(--ink)",
            border: "1px solid var(--card-border)",
            borderRadius: "var(--radius)",
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "inherit",
            flexShrink: 0,
            transition: "background .15s, color .15s",
          }}
        >
          {copied ? t.imageCreator.copied : t.imageCreator.copyLink}
        </button>
        {onDownload && (
          <button
            onClick={onDownload}
            style={{
              padding: "6px 12px",
              background: "var(--card-bg)",
              color: "var(--ink)",
              border: "1px solid var(--card-border)",
              borderRadius: "var(--radius)",
              fontSize: 12,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "inherit",
              flexShrink: 0,
            }}
          >
            {t.imageCreator.download}
          </button>
        )}
        <button
          onClick={onClose}
          style={{
            padding: "6px 14px",
            background: "var(--accent)",
            color: "white",
            border: "none",
            borderRadius: "var(--radius)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "inherit",
            flexShrink: 0,
          }}
        >
          {t.imageCreator.done}
        </button>
      </div>
    </div>
  );
}
