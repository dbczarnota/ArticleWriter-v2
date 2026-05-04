import { UserMenu } from "./UserMenu";
import { Logo } from "./Logo";

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
      <Logo />
      <UserMenu onSettings={onSettings} />
    </header>
  );
}
