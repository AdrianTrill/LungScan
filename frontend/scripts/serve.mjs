// GitHub Pages in miniature, for the scripts: the static site under a base path, with
// directories served by their index.html and missing files by 404.html.
import { existsSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".json": "application/json",
  ".wasm": "application/wasm",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".txt": "text/plain",
  ".onnx": "application/octet-stream",
};

export async function serve(site, base = "/LungScan") {
  const server = createServer((request, response) => {
    const url = new URL(request.url, "http://localhost");
    if (!url.pathname.startsWith(base)) {
      response.writeHead(404).end();
      return;
    }
    let path = normalize(join(site, decodeURIComponent(url.pathname.slice(base.length))));
    if (existsSync(path) && statSync(path).isDirectory()) path = join(path, "index.html");
    if (!existsSync(path)) path = join(site, "404.html");
    response.writeHead(path.endsWith("404.html") ? 404 : 200, {
      "Content-Type": TYPES[extname(path)] ?? "application/octet-stream",
    });
    response.end(readFileSync(path));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    origin: `http://127.0.0.1:${server.address().port}${base}`,
    close: () => server.close(),
  };
}

export function findChrome() {
  return (
    process.env.CHROME_PATH ??
    [
      "/usr/bin/google-chrome",
      "/usr/bin/google-chrome-stable",
      "/usr/bin/chromium",
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ].find(existsSync)
  );
}
