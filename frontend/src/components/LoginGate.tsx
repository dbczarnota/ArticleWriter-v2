import { useAuth } from "../lib/useAuth";
import { Logo } from "./Logo";

export function LoginGate() {
  const { login } = useAuth();
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "100vh",
      gap: 24,
    }}>
      <Logo size="lg" />
      <p style={{ color: "var(--muted)" }}>Zaloguj się, aby kontynuować</p>
      <button
        onClick={() => login()}
        style={{
          padding: "10px 24px",
          background: "var(--accent)",
          color: "var(--white)",
          border: "none",
          borderRadius: "var(--radius)",
          fontSize: 14,
          fontWeight: 500,
        }}
      >
        Zaloguj się
      </button>
    </div>
  );
}
