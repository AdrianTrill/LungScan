/** Which runtime this build uses, and where its static assets live. */

export type RuntimeMode = "server" | "browser";

export const RUNTIME: RuntimeMode =
  process.env.NEXT_PUBLIC_RUNTIME === "browser" ? "browser" : "server";

export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const REPO_URL = "https://github.com/AdrianTrill/LungScan";

/** A file under public/, with the site's base path. */
export function asset(path: string): string {
  return `${BASE_PATH}/${path.replace(/^\//, "")}`;
}
