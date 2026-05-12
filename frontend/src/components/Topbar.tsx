import { UserMenu } from "./UserMenu";
import { Logo } from "./Logo";
import { DiscoveryIcon, SettingsIcon } from "./ui/icons";
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
      height: 56,
      background: "var(--chrome-bg)",
      borderBottom: "1px solid var(--chrome-border)",
      display: "flex",
      alignItems: "center",
      padding: "0 16px 0 12px",
      justifyContent: "space-between",
      position: "sticky",
      top: 0,
      zIndex: 50,
      gap: 8,
      flexShrink: 0,
    }}>
      {/* Left: hamburger + logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          style={{
            background: "none",
            border: "none",
            padding: 6,
            cursor: "pointer",
            color: "var(--chrome-muted)",
            display: "flex",
            alignItems: "center",
            borderRadius: "var(--radius)",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--chrome-ink)"; e.currentTarget.style.background = "var(--chrome-bg2)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--chrome-muted)"; e.currentTarget.style.background = "none"; }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
        <Logo chrome />
      </div>

      {/* Right: nav + lang + user */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <NavButton onClick={onDiscovery} icon={<DiscoveryIcon />} label={t.topbar.discovery} />
        <NavButton onClick={onSettings} icon={<SettingsIcon />} label={t.topbar.settings} />

        <div style={{ display: "flex", alignItems: "center", gap: 2, padding: "0 8px", borderLeft: "1px solid var(--chrome-border)", marginLeft: 4 }}>
          {(["pl", "en"] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              style={{
                background: "none",
                border: "none",
                padding: "2px 4px",
                cursor: "pointer",
                fontSize: 11,
                fontWeight: lang === l ? 700 : 400,
                color: lang === l ? "var(--chrome-ink)" : "var(--chrome-faint)",
                letterSpacing: ".05em",
                textTransform: "uppercase",
                fontFamily: "inherit",
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

function NavButton({ onClick, icon, label }: { onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
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
        e.currentTarget.style.color = "var(--chrome-muted)";
        e.currentTarget.style.background = "transparent";
      }}
    >
      {icon}
      {label}
    </button>
  );
}
