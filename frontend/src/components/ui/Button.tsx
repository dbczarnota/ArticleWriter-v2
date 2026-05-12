import { useState } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
}

const SIZE_STYLE: Record<ButtonSize, { padding: string; fontSize: string }> = {
  sm: { padding: "6px 12px", fontSize: "13px" },
  md: { padding: "8px 16px", fontSize: "14px" },
};

const VARIANT_STYLE: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: "var(--accent)",
    color: "#fff",
    border: "1px solid var(--accent)",
  },
  outline: {
    background: "transparent",
    color: "var(--accent)",
    border: "1px solid var(--accent)",
  },
  ghost: {
    background: "transparent",
    color: "var(--ink)",
    border: "1px solid var(--card-border)",
  },
  danger: {
    background: "var(--error)",
    color: "#fff",
    border: "1px solid var(--error)",
  },
};

const HOVER_STYLE: Record<ButtonVariant, React.CSSProperties> = {
  primary: { opacity: 0.88 },
  outline: { background: "var(--accent-tint)" },
  ghost: { background: "var(--canvas-bg)", borderColor: "var(--card-border-strong)" },
  danger: { opacity: 0.88 },
};

export function Button({
  variant = "primary",
  size = "md",
  iconLeft,
  iconRight,
  style,
  type = "button",
  disabled,
  children,
  onMouseEnter,
  onMouseLeave,
  ...rest
}: ButtonProps) {
  const [hovered, setHovered] = useState(false);
  const variantStyle = VARIANT_STYLE[variant];
  const sizeStyle = SIZE_STYLE[size];
  return (
    <button
      type={type}
      disabled={disabled}
      onMouseEnter={(e) => { setHovered(true); onMouseEnter?.(e); }}
      onMouseLeave={(e) => { setHovered(false); onMouseLeave?.(e); }}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        borderRadius: "var(--radius)",
        fontWeight: 600,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        transition: "background 0.15s, color 0.15s, border-color 0.15s, opacity 0.15s",
        ...sizeStyle,
        ...variantStyle,
        ...(hovered && !disabled ? HOVER_STYLE[variant] : {}),
        ...style,
      }}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
