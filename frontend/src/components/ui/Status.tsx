import { probability } from "@/lib/format";
import type { Case } from "@/lib/types";

type Tone = "flag" | "clear" | "caution" | "muted" | "accent";

const TONES: Record<Tone, string> = {
  flag: "border-flag/30 bg-flag/10 text-flag",
  clear: "border-clear/30 bg-clear/10 text-clear",
  caution: "border-caution/30 bg-caution/10 text-caution",
  muted: "border-line-strong bg-raised text-muted",
  accent: "border-accent/30 bg-accent/10 text-accent",
};

export function Chip({
  tone = "muted",
  children,
  className = "",
  dot = false,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={`inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 text-11.5 font-medium ${TONES[tone]} ${className}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function StatusChip({ study }: { study: Case }) {
  if (study.status === "pending")
    return (
      <Chip tone="caution" dot>
        Awaiting read
      </Chip>
    );
  return study.flagged ? (
    <Chip tone="flag" dot>
      Flagged
    </Chip>
  ) : (
    <Chip tone="clear" dot>
      Cleared
    </Chip>
  );
}

/** A probability as a bar, with a tick at the 0.5 flag threshold. */
export function ProbabilityBar({
  value,
  className = "w-28",
  showValue = true,
}: {
  value: number | null;
  className?: string;
  showValue?: boolean;
}) {
  const flagged = value !== null && value >= 0.5;
  return (
    <div className="flex items-center gap-2.5">
      <div className={`relative h-1.5 overflow-hidden rounded-full bg-line ${className}`}>
        {value !== null && (
          <div
            className={`absolute inset-y-0 left-0 rounded-full ${flagged ? "bg-flag" : "bg-clear"}`}
            style={{ width: `${Math.max(2, value * 100)}%` }}
          />
        )}
        <div className="absolute inset-y-0 left-1/2 w-px bg-ink/25" />
      </div>
      {showValue && (
        <span
          className={`tabular w-12 text-right text-[12.5px] ${value === null ? "text-faint" : "text-ink"}`}
        >
          {value === null ? "–" : probability(value)}
        </span>
      )}
    </div>
  );
}

export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-strong px-6 py-14 text-center">
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {children && <p className="mt-1 max-w-md text-[12.5px] text-muted">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
