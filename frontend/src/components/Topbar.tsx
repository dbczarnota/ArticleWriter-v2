import { UserMenu } from "./UserMenu";

interface TopbarProps {
  onSettings: () => void;
}

export function Topbar({ onSettings }: TopbarProps) {
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
      <span style={{ fontWeight: 600, fontSize: 15 }}>ArticleWriter</span>
      <UserMenu onSettings={onSettings} />
    </header>
  );
}
