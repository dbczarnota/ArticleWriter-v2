interface LogoProps {
  size?: "sm" | "lg";
  chrome?: boolean;
}

export function Logo({ size = "sm", chrome = false }: LogoProps) {
  const barHeight = size === "lg" ? 36 : 22;
  const fontSize = size === "lg" ? 30 : 15;
  const textColor = chrome ? "var(--chrome-ink)" : "var(--ink)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: size === "lg" ? 16 : 10 }}>
      <div style={{ width: size === "lg" ? 5 : 3, height: barHeight, background: "var(--accent)", borderRadius: 2, flexShrink: 0 }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span style={{ fontSize, letterSpacing: "-0.03em", lineHeight: 1 }}>
          <span style={{ fontWeight: 300, color: textColor }}>headlines</span>
          <span style={{ fontWeight: 800, color: "var(--accent)" }}>forge</span>
        </span>
        {size === "sm" && (
          <span style={{ fontSize: 8, fontWeight: 500, letterSpacing: ".15em", textTransform: "uppercase", color: chrome ? "var(--chrome-subtle)" : "var(--ink-subtle)" }}>
            AI Newsroom Platform
          </span>
        )}
      </div>
    </div>
  );
}
