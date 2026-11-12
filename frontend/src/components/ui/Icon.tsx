/** Line icons on a 24px grid, drawn with the current text color. */

const PATHS = {
  worklist: "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
  patients:
    "M9 11.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4ZM3.5 19c.8-3 3-4.6 5.5-4.6s4.7 1.6 5.5 4.6M15.6 5.1a3.1 3.1 0 0 1 0 5.8M17 14.6c1.8.5 3 1.9 3.5 4.4",
  model:
    "M8 6h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2ZM10 10h4v4h-4zM9.5 2.8V6M14.5 2.8V6M9.5 18v3.2M14.5 18v3.2M2.8 9.5H6M2.8 14.5H6M18 9.5h3.2M18 14.5h3.2",
  code: "m8.5 7.5-4.5 4.5 4.5 4.5M15.5 7.5l4.5 4.5-4.5 4.5",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM12 2.8v2.1M12 19.1v2.1M2.8 12h2.1M19.1 12h2.1M5.5 5.5 7 7M17 17l1.5 1.5M5.5 18.5 7 17M17 7l1.5-1.5",
  moon: "M19.6 14.6A8 8 0 0 1 9.4 4.4a8 8 0 1 0 10.2 10.2Z",
  keyboard:
    "M5 6h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2ZM7 10h.01M10.5 10h.01M14 10h.01M17 10h.01M8 14h8",
  plus: "M12 5v14M5 12h14",
  upload: "M12 15V4M7.5 8.5 12 4l4.5 4.5M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3",
  search: "M11 17.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM20 20l-4.3-4.3",
  trash: "M4 7h16M10 4h4M6.5 7l.8 11.2a2 2 0 0 0 2 1.8h5.4a2 2 0 0 0 2-1.8L17.5 7",
  scan: "M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2M7 12h10",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6",
  download: "M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19h14",
  back: "M19 12H5M11 6l-6 6 6 6",
  prev: "m15 6-6 6 6 6",
  next: "m9 6 6 6-6 6",
  zoomIn: "M11 17.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM20 20l-4.3-4.3M11 8.5v5M8.5 11h5",
  zoomOut: "M11 17.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM20 20l-4.3-4.3M8.5 11h5",
  fit: "M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4",
  window: "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM12 4v16",
  invert:
    "M7 4h10a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3ZM4.9 19.1 19.1 4.9",
  heat: "M12 4 3 9l9 5 9-5-9-5ZM3 14l9 5 9-5",
  target:
    "M12 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM12 2v3M12 19v3M2 12h3M19 12h3",
  pan: "M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3",
  close: "m7 7 10 10M17 7 7 17",
  check: "m5 12.5 4.5 4.5L19 7",
  alert:
    "M10.3 4.3 2.9 17.5A2 2 0 0 0 4.6 20.5h14.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0ZM12 9.5v4M12 17h.01",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5M12 8h.01",
  shield: "M12 3 19 6v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3ZM9 12l2 2 4-4",
  file: "M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM14 3v5h5",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20c1-3.5 4-5.5 7.5-5.5s6.5 2 7.5 5.5",
  external: "M14 5h5v5M19 5l-8 8M17 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h4",
  server:
    "M6 4h12a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM6 13h12a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2ZM8 7.5h.01M8 16.5h.01",
  device: "M5 4h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM8 20h8M12 16v4",
  bolt: "M13 3 5 13.5h6L10 21l8-10.5h-6L13 3Z",
  reset: "M4 12a8 8 0 1 0 2.3-5.7M4 5v6h6",
  print:
    "M7 9V4h10v5M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v6H7z",
  link: "M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1",
} as const;

export type IconName = keyof typeof PATHS;

export default function Icon({
  name,
  className = "h-4 w-4",
  strokeWidth = 1.8,
}: {
  name: IconName;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`flex-none ${className}`}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
