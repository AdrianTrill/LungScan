/** Number and date formatting. The percentages match backend/app/services/analysis.py. */

export function roundHalfUp(value: number, digits = 0): number {
  const scale = 10 ** digits;
  return Math.floor(value * scale + 0.5) / scale;
}

export function percent(value: number): string {
  return `${roundHalfUp(value * 100, 1).toFixed(1)}%`;
}

/** A probability as a percentage that never rounds up to certainty. */
export function probability(value: number): string {
  if (value >= 0.9995) return ">99.9%";
  if (value > 0 && value < 0.0005) return "<0.1%";
  return percent(value);
}

export function ageFrom(dateOfBirth: string, today = new Date()): number {
  const [y, m, d] = dateOfBirth.split("-").map(Number);
  let age = today.getFullYear() - y;
  const month = today.getMonth() + 1;
  if (month < m || (month === m && today.getDate() < d)) age--;
  return age;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(iso: string, now = Date.now()): string {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} d ago`;
  return formatDate(iso);
}

export function shortId(id: string): string {
  return id.length > 12 ? id.slice(0, 8) : id;
}

export function megabytes(bytes: number): string {
  return `${(bytes / 1_000_000).toFixed(bytes < 10_000_000 ? 1 : 0)} MB`;
}
