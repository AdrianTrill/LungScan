/**
 * Two builds of one app. By default the frontend talks to the FastAPI backend. With
 * NEXT_PUBLIC_RUNTIME=browser it is exported as a static site that runs everything in
 * the page, including the model (npm run build:browser), as deployed to GitHub Pages.
 * @type {import('next').NextConfig}
 */
const browser = process.env.NEXT_PUBLIC_RUNTIME === "browser";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig = {
  reactStrictMode: true,
  trailingSlash: true,
  ...(browser && { output: "export", basePath, images: { unoptimized: true } }),
};

module.exports = nextConfig;
