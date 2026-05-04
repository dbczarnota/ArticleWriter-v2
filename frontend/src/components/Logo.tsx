interface LogoProps {
  size?: "sm" | "lg";
}

export function Logo({ size = "sm" }: LogoProps) {
  const barHeight = size === "lg" ? 36 : 20;
  const fontSize = size === "lg" ? 30 : 16;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: size === "lg" ? 16 : 10 }}>
      <div style={{ width: size === "lg" ? 5 : 3, height: barHeight, background: "#ea580c", borderRadius: 2, flexShrink: 0 }} />
      <span style={{ fontSize, letterSpacing: "-0.02em", lineHeight: 1 }}>
        <span style={{ fontWeight: 300, color: "var(--text)" }}>headlines</span>
        <span style={{ fontWeight: 800, color: "var(--text)" }}>forge</span>
        <span style={{ color: "#ea580c" }}>.</span>
      </span>
    </div>
  );
}
