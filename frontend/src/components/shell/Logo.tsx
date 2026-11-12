/** The LungScan mark: two lungs with a scan line across them (also public/favicon.svg). */
export default function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="lungscan-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2dd4bf" />
          <stop offset="1" stopColor="#0e7490" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#lungscan-logo)" />
      <path
        d="M16 6.2v6.4M16 12.6c-.5 1.5-1.6 2.4-2.9 2.8M16 12.6c.5 1.5 1.6 2.4 2.9 2.8"
        fill="none"
        stroke="#f0fdfa"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M13.5 9.1c-3.4.4-6 4.4-6.4 9.4-.3 3.4.9 5 3.1 5 2.3 0 3.8-1.3 3.8-4z"
        fill="#f0fdfa"
      />
      <path
        d="M18.5 9.1c3.4.4 6 4.4 6.4 9.4.3 3.4-.9 5-3.1 5-2.3 0-3.8-1.3-3.8-4z"
        fill="#f0fdfa"
      />
      <path
        d="M5 17.6h22"
        stroke="#042f2e"
        strokeOpacity=".55"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}
