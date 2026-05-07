import type { ReactNode } from "react";

export type StatusKind = "loading" | "empty" | "error";

interface Props {
  kind: StatusKind;
  children: ReactNode;
  /** Optional secondary line, e.g. "Try removing filters". */
  hint?: ReactNode;
}

const COLOR: Record<StatusKind, string> = {
  loading: "var(--muted)",
  empty: "var(--muted)",
  error: "var(--error-fg)",
};

export function StatusMessage({ kind, children, hint }: Props) {
  return (
    <div
      role={kind === "error" ? "alert" : undefined}
      style={{
        padding: "var(--sp-6)",
        color: COLOR[kind],
        fontSize: "var(--fs-base)",
        textAlign: "center",
      }}
    >
      <div>{children}</div>
      {hint && (
        <div style={{ marginTop: "var(--sp-2)", fontSize: "var(--fs-sm)", color: "var(--muted)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}
