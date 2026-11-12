"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { API_URL, REPO_URL, RUNTIME } from "@/lib/config";
import { useShortcuts, useTheme } from "@/lib/hooks";
import { routes } from "@/lib/routes";
import Icon, { type IconName } from "../ui/Icon";
import Logo from "./Logo";
import ShortcutsDialog from "./ShortcutsDialog";

const NAV: { href: string; label: string; icon: IconName; match: (path: string) => boolean }[] = [
  {
    href: routes.worklist,
    label: "Worklist",
    icon: "worklist",
    match: (p) => p === "/" || p.startsWith("/case"),
  },
  {
    href: routes.patients,
    label: "Patients",
    icon: "patients",
    match: (p) => p.startsWith("/patient"),
  },
  { href: routes.model, label: "Model", icon: "model", match: (p) => p.startsWith("/model") },
];

function RuntimeCard() {
  const reset = async () => {
    if (
      !confirm(
        "Delete every study, patient, and note in this browser, and start over with the samples?"
      )
    )
      return;
    await api.reset?.();
    toast.success("Started over with the sample studies");
    window.location.reload();
  };
  if (RUNTIME === "browser") {
    return (
      <div className="rounded-xl border border-accent/25 bg-accent/[0.07] p-3">
        <div className="flex items-center gap-2 text-[12.5px] font-semibold text-accent">
          <Icon name="shield" className="h-4 w-4" />
          On-device mode
        </div>
        <p className="mt-1.5 text-[12px] leading-snug text-ink-2">
          Scans, notes, and the model stay in this browser. Nothing is uploaded.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-2 text-11.5 font-medium text-muted underline-offset-2 hover:text-ink hover:underline"
        >
          Reset demo data
        </button>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-line bg-raised/60 p-3">
      <div className="flex items-center gap-2 text-[12.5px] font-semibold text-ink">
        <Icon name="server" className="h-4 w-4 text-accent" />
        Server mode
      </div>
      <p className="mt-1.5 break-all font-mono text-11 leading-snug text-muted">{API_URL}</p>
    </div>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [theme, toggleTheme] = useTheme();
  const [help, setHelp] = useState(false);
  useShortcuts({ "?": () => setHelp(true), t: toggleTheme, T: toggleTheme });

  const tools = (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={toggleTheme}
        className="rounded-lg p-2 text-muted hover:bg-line/60 hover:text-ink"
        title={`Switch to the ${theme === "dark" ? "light" : "dark"} theme (T)`}
        aria-label={`Switch to the ${theme === "dark" ? "light" : "dark"} theme`}
        data-testid="theme-toggle"
      >
        <Icon name={theme === "dark" ? "sun" : "moon"} />
      </button>
      <button
        type="button"
        onClick={() => setHelp(true)}
        className="rounded-lg p-2 text-muted hover:bg-line/60 hover:text-ink"
        title="Keyboard shortcuts (?)"
        aria-label="Keyboard shortcuts"
      >
        <Icon name="keyboard" />
      </button>
      <a
        href={REPO_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded-lg p-2 text-muted hover:bg-line/60 hover:text-ink"
        title="Source on GitHub"
        aria-label="Source on GitHub"
      >
        <Icon name="code" />
      </a>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="no-print sticky top-0 hidden h-screen w-[236px] flex-none flex-col border-r border-line bg-surface/70 px-3 py-4 backdrop-blur lg:flex">
        <Link href={routes.worklist} className="flex items-center gap-2.5 px-2">
          <Logo className="h-8 w-8" />
          <span>
            <span className="block text-[15px] font-semibold leading-tight tracking-tight text-ink">
              LungScan
            </span>
            <span className="block text-11 leading-tight text-muted">CT reading room</span>
          </span>
        </Link>
        <nav className="mt-7 space-y-0.5" aria-label="Main">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition ${
                  active ? "bg-line/60 text-ink" : "text-ink-2 hover:bg-line/40 hover:text-ink"
                }`}
              >
                {active && (
                  <span className="absolute -left-3 top-2 h-5 w-[3px] rounded-r bg-accent" />
                )}
                <Icon name={item.icon} className={`h-4 w-4 ${active ? "text-accent" : ""}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-3">
          <RuntimeCard />
          <div className="flex items-center justify-between px-1">{tools}</div>
          <p className="px-2 text-10.5 leading-snug text-faint">
            Research software. Not a medical device; not for diagnosis.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-surface/85 px-3 py-2 backdrop-blur lg:hidden">
          <Link href={routes.worklist} className="flex items-center gap-2" aria-label="LungScan">
            <Logo className="h-7 w-7" />
          </Link>
          <nav className="flex flex-1 items-center gap-0.5" aria-label="Main">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium ${
                  item.match(pathname) ? "bg-line/70 text-ink" : "text-ink-2"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          {tools}
        </header>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
      <ShortcutsDialog open={help} onClose={() => setHelp(false)} />
    </div>
  );
}
