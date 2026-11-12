"use client";

import { useEffect, useRef, type ReactNode } from "react";
import Icon from "./Icon";

/** A modal dialog. Escape and a click outside close it; focus moves into it. */
export default function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const first = panel.current?.querySelector<HTMLElement>(
      "input, select, textarea, button:not([data-close])"
    );
    first?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/55 p-4 pt-[12vh] backdrop-blur-[2px]"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      data-dialog-open
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full animate-rise rounded-2xl border border-line bg-surface shadow-pop ${
          wide ? "max-w-2xl" : "max-w-lg"
        }`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
            {description && <p className="mt-0.5 text-[12.5px] text-muted">{description}</p>}
          </div>
          <button
            type="button"
            data-close
            onClick={onClose}
            className="-mr-1 rounded-md p-1 text-muted hover:bg-line/60 hover:text-ink"
            aria-label="Close"
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
