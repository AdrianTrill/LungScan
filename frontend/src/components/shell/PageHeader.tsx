import type { ReactNode } from "react";

export default function PageHeader({
  eyebrow,
  title,
  children,
  actions,
}: {
  eyebrow?: string;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="mt-1 text-[24px] font-semibold tracking-tight text-ink">{title}</h1>
        {children && <div className="mt-1 text-[13px] text-muted">{children}</div>}
      </div>
      {actions && <div className="flex flex-none flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
