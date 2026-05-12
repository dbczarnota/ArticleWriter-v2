import { useEffect, useRef, useState } from "react";
import { useAuth } from "../lib/useAuth";
import { useT } from "../i18n";

interface UserMenuProps {
  onSettings: () => void;
}

export function UserMenu({ onSettings }: UserMenuProps) {
  const { user, logout } = useAuth();
  const t = useT();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "??";

  return (
    <div ref={wrapperRef} style={{ position: "relative", marginLeft: 4 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          background: "var(--chrome-bg2)",
          border: "1px solid var(--chrome-border)",
          color: "var(--chrome-ink)",
          fontSize: 12,
          fontWeight: 500,
          padding: "5px 10px 5px 5px",
          borderRadius: 999,
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        <span style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          background: "linear-gradient(135deg, var(--accent), var(--accent-light))",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontSize: 9,
          fontWeight: 700,
          flexShrink: 0,
        }}>
          {initials}
        </span>
        <span style={{ maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {user?.email ?? t.userMenu.account}
        </span>
        <span style={{ fontSize: 9, color: "var(--chrome-subtle)" }}>▾</span>
      </button>
      {open && (
        <div
          role="menu"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            background: "var(--chrome-bg2)",
            border: "1px solid var(--chrome-border)",
            borderRadius: "var(--radius)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
            minWidth: 160,
            zIndex: 100,
            overflow: "hidden",
          }}
        >
          <button
            role="menuitem"
            onClick={() => { setOpen(false); onSettings(); }}
            style={{
              display: "block",
              width: "100%",
              padding: "9px 16px",
              textAlign: "left",
              background: "none",
              border: "none",
              fontSize: 13,
              color: "var(--chrome-ink)",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,.06)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
          >
            {t.userMenu.settings}
          </button>
          <button
            role="menuitem"
            onClick={() => logout()}
            style={{
              display: "block",
              width: "100%",
              padding: "9px 16px",
              textAlign: "left",
              background: "none",
              border: "none",
              borderTop: "1px solid var(--chrome-border)",
              fontSize: 13,
              color: "var(--chrome-subtle)",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,.06)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
          >
            {t.userMenu.logout}
          </button>
        </div>
      )}
    </div>
  );
}
