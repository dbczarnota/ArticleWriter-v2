import { useState, useRef, useEffect } from "react";
import { useT } from "../i18n";

interface ToolsMenuProps {
  onCreateImage: () => void;
}

export function ToolsMenu({ onCreateImage }: ToolsMenuProps) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e: MouseEvent) {
      if (
        menuRef.current &&
        buttonRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div style={{ position: "relative" }}>
      <button
        ref={buttonRef}
        onClick={() => setOpen(!open)}
        style={{
          background: "transparent",
          border: "1px solid transparent",
          color: "var(--chrome-muted)",
          fontSize: 13,
          fontWeight: 500,
          padding: "7px 12px",
          borderRadius: "var(--radius)",
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontFamily: "inherit",
          transition: "color .15s, background .15s",
          whiteSpace: "nowrap",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "var(--chrome-ink)";
          e.currentTarget.style.background = "var(--chrome-bg2)";
        }}
        onMouseLeave={(e) => {
          if (!open) {
            e.currentTarget.style.color = "var(--chrome-muted)";
            e.currentTarget.style.background = "transparent";
          }
        }}
      >
        🔧
        {t.topbar.tools}
      </button>

      {open && (
        <div
          ref={menuRef}
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            background: "var(--chrome-bg)",
            border: "1px solid var(--chrome-border)",
            borderRadius: "var(--radius)",
            boxShadow: "0 2px 8px rgba(0, 0, 0, 0.12)",
            zIndex: 1000,
            minWidth: 200,
          }}
        >
          <button
            onClick={() => {
              onCreateImage();
              setOpen(false);
            }}
            style={{
              display: "block",
              width: "100%",
              padding: "10px 14px",
              textAlign: "left",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              fontSize: 13,
              color: "var(--chrome-ink)",
              fontFamily: "inherit",
              transition: "background .15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--chrome-bg2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            🖼️ {t.topbar.createImage}
          </button>
        </div>
      )}
    </div>
  );
}
