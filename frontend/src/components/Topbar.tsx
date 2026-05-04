import { UserMenu } from "./UserMenu";
import { Logo } from "./Logo";
import { useLang } from "../i18n";

interface TopbarProps {
  onSettings: () => void;
}

export function Topbar({ onSettings }: TopbarProps) {
  const { lang, setLang } = useLang();

  return (
    <header style={{
      height: 48,
      background: "var(--white)",
      borderBottom: "1px solid var(--border)",
      display: "flex",
      alignItems: "center",
      padding: "0 16px",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 50,
    }}>
      <Logo />
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ display: "flex", gap: 4, fontSize: 12, color: "var(--muted)" }}>
          {(["pl", "en"] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              style={{
                background: "none",
                border: "none",
                padding: "2px 4px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: lang === l ? 700 : 400,
                color: lang === l ? "var(--text)" : "var(--muted)",
              }}
            >
              {l}
            </button>
          ))}
        </div>
        <UserMenu onSettings={onSettings} />
      </div>
    </header>
  );
}
