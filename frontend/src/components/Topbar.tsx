import { UserMenu } from "./UserMenu";
import { Logo } from "./Logo";
import { Button } from "./ui/Button";
import { SettingsIcon } from "./ui/icons";
import { useLang, useT } from "../i18n";

interface TopbarProps {
  onSettings: () => void;
  onDiscovery: () => void;
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
}

export function Topbar({ onSettings, onDiscovery, onToggleSidebar, sidebarOpen }: TopbarProps) {
  const { lang, setLang } = useLang();
  const t = useT();

  return (
    <header style={{
      height: 48,
      background: "var(--bg2)",
      borderBottom: "1px solid var(--border)",
      display: "flex",
      alignItems: "center",
      padding: "0 12px",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 50,
      gap: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          style={{
            background: "none",
            border: "none",
            padding: 6,
            cursor: "pointer",
            color: "var(--muted)",
            display: "flex",
            alignItems: "center",
            borderRadius: "var(--radius)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--accent-lt)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
        >
          {/* Hamburger icon — three horizontal lines */}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
        <Logo />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Button variant="ghost" size="sm" onClick={onDiscovery}>
          {t.topbar.discovery}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onSettings}
          iconLeft={<SettingsIcon />}
          title={t.topbar.settings}
          aria-label={t.topbar.settings}
        >
          {t.topbar.settings}
        </Button>
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
