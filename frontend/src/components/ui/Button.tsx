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
    color: "var(--white)",
    border: "1px solid var(--accent)",
  },
  outline: {
    background: "var(--white)",
    color: "var(--accent)",
    border: "1px solid var(--accent)",
  },
  ghost: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
  },
  danger: {
    background: "var(--error)",
    color: "var(--white)",
    border: "1px solid var(--error)",
  },
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
  ...rest
}: ButtonProps) {
  const variantStyle = VARIANT_STYLE[variant];
  const sizeStyle = SIZE_STYLE[size];
  return (
    <button
      type={type}
      disabled={disabled}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        borderRadius: "var(--radius)",
        fontWeight: 500,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        transition: "background 0.15s, color 0.15s, border-color 0.15s",
        ...sizeStyle,
        ...variantStyle,
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
