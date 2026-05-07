import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  prominent?: boolean;
  children: React.ReactNode;
}

// 10×10 chevron SVG that rotates 90° when open. Replaces the previous
// ▼/▶ unicode arrows whose weight rendered inconsistently across
// macOS/Windows/Linux at the small font sizes the disclosure uses.
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

export function CollapsibleSection({ title, count, defaultOpen = false, prominent = false, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const label = count !== undefined ? `${title} (${count})` : title;

  if (prominent) {
    return (
      <section style={{ marginBottom: 24 }}>
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          style={{
            background: "none",
            border: "none",
            borderBottom: open ? "1px solid var(--border)" : "none",
            width: "100%",
            textAlign: "left",
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 0",
            marginBottom: open ? 12 : 0,
            fontSize: 14,
            fontWeight: 600,
            color: "var(--text)",
            cursor: "pointer",
          }}
        >
          <span style={{ color: "var(--muted)", flexShrink: 0, display: "inline-flex" }}>
            <Chevron open={open} />
          </span>
          {label}
        </button>
        {open && <div>{children}</div>}
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
          color: "var(--muted)",
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
