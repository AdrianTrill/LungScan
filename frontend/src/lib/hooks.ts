"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { asset } from "./config";

/** Load data on mount and when `deps` change; `reload` loads it again. */
export function useResource<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const loader = useRef(load);
  loader.current = load;

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await loader.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload, setData };
}

/** Whether keyboard shortcuts should ignore this event: typing, or a modifier held. */
export function isTyping(event: KeyboardEvent): boolean {
  if (event.metaKey || event.ctrlKey || event.altKey) return true;
  const target = event.target as HTMLElement | null;
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

/** Bind single keys (as in KeyboardEvent.key) to actions while the component is mounted. */
export function useShortcuts(bindings: Record<string, (event: KeyboardEvent) => void>) {
  const current = useRef(bindings);
  current.current = bindings;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTyping(event) || document.querySelector("[data-dialog-open]")) return;
      const action = current.current[event.key];
      if (action) {
        event.preventDefault();
        action(event);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

export type Theme = "dark" | "light";

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>("dark");
  useEffect(() => {
    setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
  }, []);
  const toggle = useCallback(() => {
    setTheme((previous) => {
      const next = previous === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem("lungscan-theme", next);
      } catch {
        // Without storage the choice lasts for this page only.
      }
      return next;
    });
  }, []);
  return [theme, toggle];
}

export interface Evaluation {
  clean_test: {
    images: number;
    cancer_vs_normal: {
      sensitivity: { k: number; n: number; ci95: number[] };
      specificity: { k: number; n: number; ci95: number[] };
      auc: number;
    };
    four_class: {
      accuracy: number;
      confusion: number[][];
      per_class: Record<string, { precision: number; recall: number; f1: number; support: number }>;
    };
    subtype_on_cancers: { k: number; n: number; accuracy: number; chance: number };
  };
  data: {
    images: Record<string, number>;
    test_removed: Record<string, number>;
    clean_test_per_class: Record<string, number>;
  };
}

let evaluation: Promise<Evaluation | null> | null = null;

/** The model's measured performance (model/evaluation.json, copied into public/). */
export function useEvaluation(): Evaluation | null {
  const [value, setValue] = useState<Evaluation | null>(null);
  useEffect(() => {
    evaluation ??= fetch(asset("evaluation.json"))
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
    void evaluation.then(setValue);
  }, []);
  return value;
}
