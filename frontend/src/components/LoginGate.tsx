import { useAuth } from "../lib/useAuth";

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
      <h1 style={{ fontSize: 24, fontWeight: 600 }}>ArticleWriter</h1>
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
