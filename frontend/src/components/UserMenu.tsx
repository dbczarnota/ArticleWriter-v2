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

  return (
    <div ref={wrapperRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        style={{
          background: "none",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "4px 10px",
          fontSize: 13,
          color: "var(--text)",
        }}
      >
        {user?.email ?? t.userMenu.account} ▾
      </button>
      {open && (
        <div
          role="menu"
          style={{
          position: "absolute",
          right: 0,
          top: "calc(100% + 4px)",
          background: "var(--bg2)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          minWidth: 160,
          zIndex: 100,
          overflow: "hidden",
        }}>
          <button
            role="menuitem"
            onClick={() => { setOpen(false); onSettings(); }}
            style={{ display: "block", width: "100%", padding: "8px 16px", textAlign: "left", background: "none", border: "none", fontSize: 13 }}
          >
            {t.userMenu.settings}
          </button>
          <button
            role="menuitem"
            onClick={() => logout()}
            style={{ display: "block", width: "100%", padding: "8px 16px", textAlign: "left", background: "none", border: "none", fontSize: 13, color: "var(--muted)" }}
          >
            {t.userMenu.logout}
          </button>
        </div>
      )}
    </div>
  );
}
