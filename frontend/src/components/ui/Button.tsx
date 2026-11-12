import type { ButtonHTMLAttributes, ReactNode } from "react";
import Icon, { type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-ink hover:brightness-110 shadow-[0_8px_24px_-12px_rgb(var(--accent)/0.7)]",
  secondary: "border border-line bg-raised text-ink hover:border-line-strong hover:bg-line/40",
  ghost: "text-ink-2 hover:bg-line/50 hover:text-ink",
  danger: "border border-flag/30 bg-flag/10 text-flag hover:bg-flag/15",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  icon?: IconName;
  shortcut?: string;
  children?: ReactNode;
}

export default function Button({
  variant = "secondary",
  size = "md",
  icon,
  shortcut,
  children,
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  const sizing =
    size === "sm" ? "h-8 gap-1.5 px-2.5 text-[12.5px]" : "h-9 gap-2 px-3.5 text-[13px]";
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition duration-150 disabled:pointer-events-none disabled:opacity-45 ${sizing} ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {icon && <Icon name={icon} className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} />}
      {children}
      {shortcut && (
        <span
          className={`ml-0.5 hidden rounded px-1 font-mono text-[10.5px] sm:inline ${
            variant === "primary" ? "bg-black/15" : "bg-line/70 text-muted"
          }`}
        >
          {shortcut}
        </span>
      )}
    </button>
  );
}
