import { useState } from "react";

interface CollapsibleSectionProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  prominent?: boolean;
  children: React.ReactNode;
}

export function CollapsibleSection({ title, count, defaultOpen = false, prominent = false, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const label = count !== undefined ? `${title} (${count})` : title;

  if (prominent) {
    return (
      <section style={{ marginBottom: 24 }}>
        <button
          onClick={() => setOpen((o) => !o)}
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
            color: "var(--fg, #1a1a1a)",
            cursor: "pointer",
          }}
        >
          <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 400, flexShrink: 0 }}>{open ? "▼" : "▶"}</span>
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
        <span style={{ fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        {label}
      </button>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
    </div>
  );
}
