import { useState } from "react";
import { useAuth } from "../lib/useAuth";
import { useT } from "../i18n";

interface UserMenuProps {
  onSettings: () => void;
}

export function UserMenu({ onSettings }: UserMenuProps) {
  const { user, logout } = useAuth();
  const t = useT();
  const [open, setOpen] = useState(false);

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((o) => !o)}
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
        <div style={{
          position: "absolute",
          right: 0,
          top: "calc(100% + 4px)",
          background: "var(--white)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          minWidth: 160,
          zIndex: 100,
          overflow: "hidden",
        }}>
          <button
            onClick={() => { setOpen(false); onSettings(); }}
            style={{ display: "block", width: "100%", padding: "8px 16px", textAlign: "left", background: "none", border: "none", fontSize: 13 }}
          >
            {t.userMenu.settings}
          </button>
          <button
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
