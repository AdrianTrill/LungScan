// Drives the static in-browser build in headless Chrome, the way a visitor would, and
// fails on the first thing that does not work. The Pages workflow runs it before deploying.
//
//   npm run build:browser            (with NEXT_PUBLIC_BASE_PATH=/LungScan)
//   node scripts/ui-check.mjs out [--screenshots dir]
//
// Chrome comes from CHROME_PATH, or the usual install locations.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import puppeteer from "puppeteer-core";
import { findChrome, serve } from "./serve.mjs";

const args = process.argv.slice(2);
const site = args[0] ?? "out";
const shotsAt = args.indexOf("--screenshots");
const shots = shotsAt >= 0 ? args[shotsAt + 1] : null;
if (shots) mkdirSync(shots, { recursive: true });
const samples = JSON.parse(readFileSync(join(site, "samples", "samples.json"), "utf8"));

const server = await serve(site);
const origin = server.origin;
const chrome = findChrome();
const browser = await puppeteer.launch({
  executablePath: chrome,
  headless: true,
  args: ["--no-sandbox", "--disable-gpu"],
});

const problems = [];
let passed = 0;
async function check(name, run) {
  try {
    await run();
    passed++;
    console.log(`  ok    ${name}`);
  } catch (error) {
    problems.push(`${name}: ${error.message}`);
    console.log(`  FAIL  ${name}: ${error.message}`);
  }
}
function expect(condition, message) {
  if (!condition) throw new Error(message);
}

const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900 });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(e.message));
page.on("requestfailed", (r) => errors.push(`${r.url()}: ${r.failure()?.errorText}`));
page.on("response", (r) => r.status() >= 400 && errors.push(`${r.url()}: HTTP ${r.status()}`));

const go = (path) => page.goto(`${origin}${path}`, { waitUntil: "networkidle0" });
const text = () => page.evaluate(() => document.body.innerText);
const rows = () => page.$$eval('[data-testid="study-row"]', (r) => r.length);
const shot = async (name) => shots && page.screenshot({ path: join(shots, `${name}.png`) });
const cancerProbability = () =>
  page.$eval('[data-testid="verdict"]', (el) => Number(el.dataset.cancerProbability));
const waitForRead = () =>
  page.waitForFunction(() => !document.querySelector('[data-testid="analysis-progress"]'), {
    timeout: 180_000,
  });

console.log(`Checking ${origin} in ${chrome}`);

await check("the worklist starts with the sample studies", async () => {
  await go("/");
  await page.waitForSelector('[data-testid="study-row"]');
  expect((await rows()) === samples.cases.length, `${await rows()} rows`);
  const flagged = samples.cases.filter((c) => c.result.flagged).length;
  const tab = await page.$eval('[role="tab"]:nth-child(2)', (el) => el.textContent);
  expect(tab === `Flagged${flagged}`, `the Flagged tab reads ${tab}`);
  await shot("worklist");
});

await check("filters, search, and the keyboard move through the worklist", async () => {
  await page.click('[role="tab"]:nth-child(2)');
  const flagged = samples.cases.filter((c) => c.result.flagged).length;
  expect((await rows()) === flagged, `the Flagged filter shows ${await rows()} rows`);
  await page.click('[role="tab"]:nth-child(1)');
  await page.keyboard.press("/");
  await page.keyboard.type("Smith");
  expect((await rows()) === 2, `searching for Smith shows ${await rows()} rows`);
  await page.keyboard.press("Escape");
  await page.keyboard.press("j");
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle0" }),
    page.keyboard.press("Enter"),
  ]);
  expect(page.url().includes("id=sample-02"), `Enter opened ${page.url()}`);
});

await check("a sample opens with its precomputed read and heat map", async () => {
  await go("/case/?id=sample-01");
  await page.waitForSelector('[data-testid="verdict"]');
  const want = samples.cases.find((c) => c.id === "sample-01").result;
  expect((await cancerProbability()) === want.cancer_probability, "the cancer probability differs");
  await page.waitForFunction(() => {
    const canvas = document.querySelector('[data-testid="heatmap"]');
    if (!canvas || !canvas.width) return false;
    const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    for (let i = 3; i < data.length; i += 4) if (data[i] > 0) return true;
    return false;
  });
  expect(
    (await text()).includes("The read agrees with the dataset label"),
    "no dataset label check"
  );
  await shot("study");
});

await check("the model runs in this browser and agrees with the server", async () => {
  for (const id of ["sample-01", "sample-06"]) {
    await go(`/case/?id=${id}`);
    await page.waitForSelector('[data-testid="analyze"]');
    await page.click('[data-testid="analyze"]');
    await waitForRead();
    const got = await cancerProbability();
    const want = samples.cases.find((c) => c.id === id).result.cancer_probability;
    expect(Math.abs(got - want) <= 1e-4, `${id}: the browser read ${got}, the server ${want}`);
    expect((await text()).includes("this browser)"), `${id}: the read did not run in this browser`);
    console.log(`        ${id}: browser ${got}, server ${want}`);
  }
  await shot("study-read-in-browser");
});

await check("a new study is uploaded and read straight away", async () => {
  await go("/");
  await page.waitForSelector('[data-testid="study-row"]');
  await page.keyboard.press("n");
  await page.waitForSelector('[data-testid="dropzone"]');
  await page.click('button[title="Use sample-05"]');
  await page.waitForFunction(() => document.body.innerText.includes("sample-05.png"));
  const [button] = await page.$$("xpath/.//button[contains(., 'Add and read')]");
  await Promise.all([page.waitForNavigation({ waitUntil: "networkidle0" }), button.click()]);
  await page.waitForSelector('[data-testid="verdict"]', { timeout: 180_000 });
  await waitForRead();
  const want = samples.cases.find((c) => c.id === "sample-05").result.cancer_probability;
  expect(
    Math.abs((await cancerProbability()) - want) <= 1e-4,
    "the uploaded slice reads differently"
  );
  await go("/");
  expect((await rows()) === samples.cases.length + 1, `${await rows()} rows after the upload`);
});

await check("notes are saved and survive a reload", async () => {
  await go("/case/?id=sample-04");
  await page.waitForSelector('textarea[aria-label="Notes"]');
  await page.type('textarea[aria-label="Notes"]', " Checked by the UI test.");
  await page.waitForFunction(() => document.body.innerText.includes("Saved"), { timeout: 5000 });
  await new Promise((r) => setTimeout(r, 800));
  await go("/case/?id=sample-04");
  const notes = await page.$eval('textarea[aria-label="Notes"]', (el) => el.value);
  expect(notes.includes("Checked by the UI test."), "the notes were lost");
});

await check("the viewer and the shortcuts respond", async () => {
  await go("/case/?id=sample-02");
  await page.waitForSelector('[data-testid="heatmap"]');
  await page.keyboard.press("i");
  const inverted = await page.$eval('button[aria-label="Invert"]', (b) =>
    b.getAttribute("aria-pressed")
  );
  expect(inverted === "true", "I did not invert the slice");
  await page.keyboard.press("h");
  const opacity = await page.$eval('[data-testid="heatmap"]', (c) => c.style.opacity);
  expect(opacity === "0", "H did not hide the heat map");
  const theme = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.keyboard.press("t");
  const next = await page.evaluate(() => document.documentElement.dataset.theme);
  expect(theme !== next, "T did not switch the theme");
  await page.keyboard.press("?");
  await page.waitForSelector('[role="dialog"][aria-label="Keyboard shortcuts"]');
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  await page.keyboard.press("t");
});

await check("the model page shows the measured performance", async () => {
  await go("/model/");
  await page.waitForFunction(() => document.body.innerText.includes("Cancers flagged"));
  const evaluation = JSON.parse(readFileSync(join(site, "evaluation.json"), "utf8")).clean_test;
  const s = evaluation.cancer_vs_normal.sensitivity;
  expect((await text()).includes(`${s.k} / ${s.n}`), "the sensitivity is missing");
  await shot("model");
});

await check("pages fit a phone's screen", async () => {
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
  for (const path of ["/", "/case/?id=sample-01", "/patients/", "/model/"]) {
    await go(path);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow <= 0, `${path} is ${overflow}px wider than the screen`);
  }
  await shot("phone");
});

await check("nothing logged an error or failed to load", async () => {
  expect(errors.length === 0, `\n    ${errors.join("\n    ")}`);
});

await browser.close();
server.close();
console.log(`${passed} passed, ${problems.length} failed`);
process.exit(problems.length ? 1 : 0);
