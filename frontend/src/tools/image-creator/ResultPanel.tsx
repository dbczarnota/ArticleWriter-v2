import { useT } from "../../i18n";

interface ResultPanelProps {
  url: string;
  onClose: () => void;
  onDownload?: () => void;
}

export function ResultPanel({ url, onClose, onDownload }: ResultPanelProps) {
  const t = useT();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "24px" }}>
      <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
        {t.imageCreator.resultTitle}
      </h3>

      <img
        src={url}
        alt="Generated image"
        style={{
          maxWidth: "100%",
          height: "auto",
          borderRadius: "var(--radius)",
          border: "1px solid var(--border)",
        }}
      />

      <div style={{ display: "flex", gap: 8 }}>
        {onDownload && (
          <button
            onClick={onDownload}
            style={{
              flex: 1,
              padding: "8px 12px",
              background: "var(--chrome-bg2)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            💾 {t.imageCreator.download}
          </button>
        )}
        <button
          onClick={onClose}
          style={{
            flex: 1,
            padding: "8px 12px",
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
          {t.imageCreator.done}
        </button>
      </div>
    </div>
  );
}
