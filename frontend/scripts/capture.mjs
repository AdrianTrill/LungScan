// Regenerates the README's images and the link-preview card from the in-browser build:
//
//   npm run build:browser            (with NEXT_PUBLIC_BASE_PATH=/LungScan)
//   node scripts/capture.mjs out
//
// Writes docs/assets/{reading-room.png, worklist.png, model.png, demo.gif} and
// public/social.png (copy it into out/ or rebuild). Needs Chrome, and ffmpeg for the GIF.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";
import { findChrome, serve } from "./serve.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const site = process.argv[2] ?? "out";
const assets = join(here, "..", "..", "docs", "assets");
mkdirSync(assets, { recursive: true });
const server = await serve(site);
const browser = await puppeteer.launch({
  executablePath: findChrome(),
  headless: true,
  args: ["--enable-unsafe-webgpu", "--hide-scrollbars"],
});
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function open(path, { theme = "dark", width = 1280, height = 800, scale = 1.5625 } = {}) {
  const context = await browser.createBrowserContext();
  const page = await context.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: scale });
  await page.evaluateOnNewDocument((t) => localStorage.setItem("lungscan-theme", t), theme);
  await page.goto(`${server.origin}${path}`, { waitUntil: "networkidle0" });
  return page;
}

async function readInBrowser(page) {
  await page.click('[data-testid="analyze"]');
  await page.waitForFunction(
    () =>
      !document.querySelector('[data-testid="analysis-progress"]') &&
      document.body.innerText.includes("this browser)"),
    { timeout: 180_000 }
  );
  await page.mouse.move(0, 0);
  await wait(900);
}

// The reading room, after a read in the browser, with the region highlighted.
const study = await open("/case/?id=sample-01");
await readInBrowser(study);
await study.waitForFunction(() => !document.body.innerText.includes("Read complete"), {
  timeout: 10_000,
});
const region = await study.$('button[title="Show this region in the viewer"]');
await region.hover();
await wait(400);
await study.screenshot({ path: join(assets, "reading-room.png") });
const probability = await study.$eval('[data-testid="verdict"]', (el) =>
  Number(el.dataset.cancerProbability)
);
const runtime = await study.evaluate(() =>
  document.body.innerText.includes("WebGPU") ? "WebGPU" : "WebAssembly"
);
const ms = await study.evaluate(
  () => document.body.innerText.match(/Inference\s+([\d.]+) ms/)?.[1]
);
console.log(`reading-room.png: ${probability} on ${runtime}, ${ms} ms`);

// The slice and its heat map alone, for the card.
await study.setViewport({ width: 1500, height: 1100, deviceScaleFactor: 2 });
await study.keyboard.press("f");
await wait(600);
const box = await study.$eval('[data-testid="viewer"] img', (img) => {
  const r = img.getBoundingClientRect();
  return { x: r.x, y: r.y, width: r.width, height: r.height };
});
const side = Math.min(box.width, box.height);
const slice = await study.screenshot({
  clip: {
    x: box.x + (box.width - side) / 2,
    y: box.y + (box.height - side) / 2,
    width: side,
    height: side,
  },
  encoding: "base64",
});
await study.browserContext().close();

const worklist = await open("/", { theme: "light" });
await worklist.mouse.move(700, 470);
await wait(500);
await worklist.screenshot({ path: join(assets, "worklist.png") });
await worklist.browserContext().close();

const model = await open("/model/", { height: 1000 });
await wait(800);
await model.screenshot({ path: join(assets, "model.png") });
await model.browserContext().close();

// The link-preview card (public/social.png), also the README's header.
const logo = readFileSync(join(here, "..", "public", "favicon.svg"), "utf8").replace(
  "<svg ",
  '<svg width="58" height="58" '
);
const card = readFileSync(join(here, "social-card.html"), "utf8")
  .replace("{{LOGO}}", logo)
  .replace("{{SLICE}}", `data:image/png;base64,${slice}`)
  .replace("{{ARC}}", String(Math.round(2 * Math.PI * 242 * probability)))
  .replace("{{PROBABILITY}}", `${(probability * 100).toFixed(1)}%`)
  .replace("{{RUNTIME}}", `${runtime}, ${Math.round(Number(ms))} ms`);
const cardPage = await browser.newPage();
await cardPage.setViewport({ width: 1200, height: 630, deviceScaleFactor: 1 });
await cardPage.setContent(card, { waitUntil: "networkidle0" });
await cardPage.screenshot({ path: join(here, "..", "public", "social.png") });
await cardPage.close();
console.log("social.png");

// A read from a cold start: the model downloads, the slice is read, the regions explored.
const video = join(tmpdir(), "lungscan-demo.webm");
const demo = await open("/", { scale: 1 });
const cdp = await demo.createCDPSession();
await cdp.send("Network.emulateNetworkConditions", {
  offline: false,
  latency: 20,
  downloadThroughput: 48 * 1024 * 1024,
  uploadThroughput: 8 * 1024 * 1024,
});
const recorder = await demo.screencast({ path: video });
await wait(1200);
await demo.hover('[data-testid="study-row"]:nth-child(2)');
await wait(500);
await demo.hover('[data-testid="study-row"]:nth-child(1)');
await wait(500);
await Promise.all([
  demo.waitForNavigation({ waitUntil: "networkidle0" }),
  demo.click('[data-testid="study-row"]'),
]);
await wait(1400);
await demo.keyboard.press("h");
await wait(700);
await demo.keyboard.press("h");
await wait(700);
await demo.click('[data-testid="analyze"]');
await demo.waitForFunction(() => !document.querySelector('[data-testid="analysis-progress"]'), {
  timeout: 180_000,
});
await wait(1500);
const target = await demo.$('button[title="Show this region in the viewer"]');
await target.hover();
await wait(800);
await target.click();
await wait(1400);
await demo.keyboard.press("i");
await wait(900);
await demo.keyboard.press("0");
await wait(900);
await demo.keyboard.press("t");
await wait(1500);
await recorder.stop();
await demo.browserContext().close();

const gif = join(assets, "demo.gif");
execFileSync("ffmpeg", [
  "-y",
  "-loglevel",
  "error",
  "-i",
  video,
  "-vf",
  "fps=12,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
  gif,
]);
rmSync(video, { force: true });
console.log("demo.gif");

await browser.close();
server.close();
