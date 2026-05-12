import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  prominent?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        flexShrink: 0,
        transition: "transform 0.15s ease",
        transform: open ? "rotate(90deg)" : "rotate(0deg)",
      }}
      aria-hidden
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function CollapsibleSection({ title, count, defaultOpen = false, prominent = false, icon, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const label = count !== undefined ? `${title} (${count})` : title;

  if (prominent) {
    return (
      <section style={{ marginBottom: 16 }}>
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          style={{
            background: "var(--card-bg)",
            border: "1px solid var(--card-border)",
            borderRadius: open ? "var(--radius) var(--radius) 0 0" : "var(--radius)",
            width: "100%",
            textAlign: "left",
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 12px",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--ink-subtle)",
            cursor: "pointer",
          }}
        >
          {icon && (
            <span style={{
              width: 24,
              height: 24,
              borderRadius: 7,
              background: "var(--accent-tint)",
              color: "var(--accent)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}>
              {icon}
            </span>
          )}
          <span style={{ flex: 1 }}>{label}</span>
          <span style={{ color: "var(--ink-subtle)", display: "inline-flex" }}>
            <Chevron open={open} />
          </span>
        </button>
        {open && (
          <div style={{
            background: "var(--card-bg)",
            border: "1px solid var(--card-border)",
            borderTop: "none",
            borderRadius: "0 0 var(--radius) var(--radius)",
            padding: "12px 14px",
          }}>
            {children}
          </div>
        )}
      </section>
    );
  }

  return (
    <div style={{ marginTop: 16 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          background: "none",
          border: "none",
          fontSize: 13,
          fontWeight: 600,
          color: "var(--ink-muted)",
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 0",
          cursor: "pointer",
        }}
      >
        <Chevron open={open} />
        {label}
      </button>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
    </div>
  );
}
