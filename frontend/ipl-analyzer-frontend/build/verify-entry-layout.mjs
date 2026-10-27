#!/usr/bin/env node
/** Browser regression: the shared footer must not enter the loading viewport.
 * PLAYWRIGHT_MODULE=/existing/playwright node build/verify-entry-layout.mjs BASE...
 * Uses installed Chromium, anonymous local previews and no sports-provider requests.
 */
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const bases = process.argv.slice(2);
if (!bases.length) throw new Error('Supply at least one local preview base URL.');
const browser = await chromium.launch({ headless: true });
try {
  for (const base of bases) for (const width of [375, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    let release;
    const held = new Promise(resolve => { release = resolve; });
    await context.route('**/data/leagues.json', async route => { await held; await route.continue(); });
    await context.route('https://sportscore.com/**', route => route.abort());
    const page = await context.newPage();
    try {
      await page.goto(base, { waitUntil: 'domcontentloaded' });
      await page.locator('.loading-shell').waitFor();
      await page.locator('.site-info-footer').waitFor();
      await page.evaluate(() => document.fonts.ready);
      const loading = await page.locator('.site-info-footer').evaluate(footer => ({ top: footer.getBoundingClientRect().top, viewport: innerHeight }));
      if (loading.top < loading.viewport - 1) throw new Error(`Footer entered loading viewport at ${loading.top}px/${loading.viewport}px: ${base}, ${width}px`);
      release();
      await page.locator('[data-testid=landing-page]').waitFor();
      const final = await page.evaluate(() => ({ footer: !!document.querySelector('.site-info-footer a[href]'), overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth + 1 }));
      if (!final.footer || final.overflow) throw new Error(`Final page lost footer or overflowed: ${base}, ${width}px`);
      console.log(`PASS ${base} ${width}px: loading footer ${loading.top}px; final footer links and geometry retained`);
    } finally { release(); await context.close(); }
  }
} finally { await browser.close(); }
