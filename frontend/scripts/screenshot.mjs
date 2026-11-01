/**
 * Screenshot the running app at desktop and phone widths.
 *
 * Exists because a UI can pass every automated gate and still be broken: the
 * design tokens were once silently dropped by a stray `*\/` in a CSS comment,
 * and the build, the typecheck, 32 tests and a grep for banned colour classes
 * all passed while the app rendered grey with an invisible primary button.
 * Only looking at it showed the problem.
 *
 * Lives under frontend/ because playwright is a frontend devDependency and
 * node resolves imports from the script's own directory, not the cwd.
 *
 * Usage (with the app running):
 *   APP_PASSWORD=... make shots      # local dev
 *   APP_URL=https://... make shots   # any deployment
 */
import { chromium, devices } from "playwright";
import { mkdir } from "node:fs/promises";

const OUT = process.argv[2] ?? "screenshots";
const BASE = process.env.APP_URL ?? "http://localhost:5173";
const EMAIL = process.env.APP_EMAIL ?? "admin@excelengineers.in";
const PASSWORD = process.env.APP_PASSWORD;
if (!PASSWORD) {
  console.error("APP_PASSWORD is not set. Run: APP_PASSWORD=... make shots");
  process.exit(1);
}

const PAGES = [
  "/inventory",
  "/products",
  "/suppliers",
  "/customers",
  "/quotations",
  "/quotations/new",
  "/quotations/1",
  "/settings",
];

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();

async function shoot(context, tag) {
  const page = await context.newPage();
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.screenshot({ path: `${OUT}/${tag}-login.png`, fullPage: true });

  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);

  for (const path of PAGES) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/${tag}${path.replace(/\//g, "-")}.png`, fullPage: true });
  }
  await page.close();
}

await shoot(await browser.newContext({ viewport: { width: 1440, height: 900 } }), "desktop");
await shoot(await browser.newContext({ ...devices["iPhone 13"] }), "mobile");

// Dark is a CSS-variable flip on [data-theme], not a set of `dark:` classes,
// so a token that only resolves in one theme is invisible until it is looked
// at in the other. Seeding localStorage before the app boots avoids a flash
// of the light palette ending up in the shot.
await shoot(
  await browser.newContext({
    viewport: { width: 1440, height: 900 },
    storageState: {
      cookies: [],
      origins: [{ origin: BASE, localStorage: [{ name: "ee-theme", value: "dark" }] }],
    },
  }),
  "dark",
);

await browser.close();
console.log(`screenshots written to ${OUT}/`);
