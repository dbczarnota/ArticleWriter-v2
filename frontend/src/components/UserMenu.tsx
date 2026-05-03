import { useState } from "react";
import { useAuth } from "../lib/useAuth";

interface UserMenuProps {
  onSettings: () => void;
}

export function UserMenu({ onSettings }: UserMenuProps) {
  const { user, logout } = useAuth();
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
        {user?.email ?? "konto"} ▾
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
            Ustawienia
          </button>
          <button
            onClick={() => logout()}
            style={{ display: "block", width: "100%", padding: "8px 16px", textAlign: "left", background: "none", border: "none", fontSize: 13, color: "var(--muted)" }}
          >
            Wyloguj
          </button>
        </div>
      )}
    </div>
  );
}
