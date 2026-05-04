interface LogoProps {
  size?: "sm" | "lg";
}

export function Logo({ size = "sm" }: LogoProps) {
  const iconSize = size === "lg" ? 40 : 22;
  const fontSize = size === "lg" ? 26 : 15;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: size === "lg" ? 12 : 8 }}>
      <svg width={iconSize} height={iconSize} viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <rect width="32" height="32" rx="7" fill="#ea580c"/>
        <path d="M16 6c-.3.4-1.2 1.7-2 3.2-1 1.8-1.8 3.8-1.8 5.8 0 .6.1 1.2.2 1.7-.5-.6-.8-1.4-.8-2.2 0-.4 0-.8.1-1.1-1.1 1.4-1.7 3.2-1.7 5.1C10 22.4 12.7 26 16 26s6-3.6 6-7.5c0-1.9-.6-3.7-1.7-5.1.1.3.1.7.1 1.1 0 .8-.3 1.6-.8 2.2.1-.5.2-1.1.2-1.7 0-2-.8-4-1.8-5.8C17.2 7.7 16.3 6.4 16 6z" fill="white"/>
        <path d="M16 18c-.1.2-.5.8-.8 1.5-.2.5-.2 1-.2 1.5 0 1.1.4 2 1 2s1-.9 1-2c0-.5-.1-1-.2-1.5C16.5 18.8 16.1 18.2 16 18z" fill="#ea580c"/>
      </svg>
      <span style={{ fontSize, lineHeight: 1 }}>
        <span style={{ fontWeight: 400, color: "var(--text)" }}>Headlines</span>
        <span style={{ fontWeight: 700, color: "#ea580c" }}>Forge</span>
      </span>
    </div>
  );
}
