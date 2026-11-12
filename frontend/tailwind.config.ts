import type { Config } from "tailwindcss";

// Every color is a theme token (src/styles/globals.css), so both themes share one set of classes.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        sunken: token("sunken"),
        raised: token("raised"),
        line: token("line"),
        "line-strong": token("line-strong"),
        ink: token("ink"),
        "ink-2": token("ink-2"),
        muted: token("muted"),
        faint: token("faint"),
        accent: token("accent"),
        "accent-ink": token("accent-ink"),
        flag: token("flag"),
        clear: token("clear"),
        caution: token("caution"),
        viewer: token("viewer"),
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Text"',
          '"Segoe UI Variable Text"',
          '"Segoe UI"',
          "Inter",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          '"SF Mono"',
          "SFMono-Regular",
          '"JetBrains Mono"',
          '"Cascadia Mono"',
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
        pop: "var(--shadow-pop)",
      },
      keyframes: {
        sweep: {
          "0%": { transform: "translateY(-10%)", opacity: "0" },
          "10%": { opacity: "1" },
          "90%": { opacity: "1" },
          "100%": { transform: "translateY(1000%)", opacity: "0" },
        },
        rise: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "none" },
        },
      },
      animation: {
        sweep: "sweep 2.2s cubic-bezier(0.45, 0, 0.55, 1) infinite",
        rise: "rise 180ms ease-out both",
      },
    },
  },
  plugins: [],
};
export default config;
