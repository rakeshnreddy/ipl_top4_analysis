#!/usr/bin/env node
/**
 * node scripts/verify_redesign.mjs https://ipl-playoff-pulse.pages.dev/ foundation
 * Optional: PLAYWRIGHT_MODULE, AXE_PATH, VERIFY_BROWSERS=chromium,webkit,
 * VERIFY_WIDTHS=320,375,1280, VERIFY_FAMILIES=landing,hub,football,cricket,f1,share.
 * Uses existing runtimes only. Exits 1 for confirmed failures, 2 for setup errors.
 */
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile, access, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const base = new URL(process.argv[2] || 'http://127.0.0.1:5180/');
if (!base.pathname.endsWith('/')) base.pathname += '/';
base.search = '';
base.hash = '';
const label = (process.argv[3] || 'local').replace(/[^a-zA-Z0-9_-]/g, '-');
const output = path.join(root, 'docs', 'screenshots', `verification-${label}`);
const widths = (process.env.VERIFY_WIDTHS || '320,375,1280').split(',').map(Number);
const engines = (process.env.VERIFY_BROWSERS || 'chromium,webkit').split(',');
const definitions = {
  landing: '', hub: '?view=hub', football: '?league=epl-2026-27',
  cricket: '?league=ipl-2026', f1: '?league=f1-2026', share: 'share.html',
};
const families = (process.env.VERIFY_FAMILIES || Object.keys(definitions).join(',')).split(',');
const report = {
  base: base.href, label, startedAt: new Date().toISOString(),
  configuration: { engines, widths, themes: ['light', 'dark'], families, reducedMotion: 'reduce' },
  axe: null, cases: [], summary: {},
  limits: ['Synthetic browser checks do not establish real-user INP.',
    'Axe and computed text sizes do not replace manual screen-reader or composited-contrast review.',
    'Inline prose links are recorded separately from the required 44px standalone controls.',
    'The route matrix uses current served payload states; it does not inject missing/error/season fixtures.'],
};

async function existing(file) { try { await access(file); return true; } catch { return false; } }
async function findAxe() {
  if (process.env.AXE_PATH) return await existing(process.env.AXE_PATH) ? process.env.AXE_PATH : null;
  const cache = path.join(os.homedir(), '.npm', '_npx');
  try {
    for (const directory of await readdir(cache)) {
      const candidate = path.join(cache, directory, 'node_modules', 'axe-core', 'axe.min.js');
      if (await existing(candidate)) return candidate;
    }
  } catch { /* Optional dependency; record absence. */ }
  return null;
}
function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright',
    path.join(os.homedir(), 'gstack', 'node_modules', 'playwright'),
    '/Users/Rakesh/gstack/node_modules/playwright'].filter(Boolean);
  const errors = [];
  for (const candidate of candidates) {
    try { return require(candidate); } catch (error) { errors.push(`${candidate}: ${error.message.split('\n')[0]}`); }
  }
  throw new Error(`No existing Playwright module found. Set PLAYWRIGHT_MODULE. ${errors.join('; ')}`);
}
async function settle(page) {
  await page.locator('main h1').first().waitFor({ state: 'visible', timeout: 15000 });
  await page.evaluate(async () => {
    await Promise.race([document.fonts.ready, new Promise((resolve) => setTimeout(resolve, 5000))]);
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}
async function domAudit(page) {
  return page.evaluate(() => {
    const describe = (element) => ({ tag: element.tagName.toLowerCase(),
      text: (element.getAttribute('aria-label') || element.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 95),
      selector: `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}${typeof element.className === 'string' && element.className ? `.${element.className.trim().split(/\s+/).join('.')}` : ''}` });
    const visible = (element) => {
      const box = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return box.width > 1 && box.height > 1 && style.visibility !== 'hidden' && style.display !== 'none'
        && !element.closest('.visually-hidden,[hidden]') && !(style.clip && style.clip !== 'auto');
    };
    const smallText = [];
    for (const element of document.querySelectorAll('body *')) {
      if (!visible(element)) continue;
      if (![...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())) continue;
      const size = parseFloat(getComputedStyle(element).fontSize);
      if (size < 11.99) smallText.push({ ...describe(element), fontSize: size });
    }
    const smallTargets = [], inlineLinks = [];
    for (const element of document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=tab]')) {
      if (!visible(element) || element.matches('.skip-link') || element.hasAttribute('disabled')) continue;
      const box = element.getBoundingClientRect();
      if (box.width >= 43.5 && box.height >= 43.5) continue;
      const item = { ...describe(element), width: +box.width.toFixed(1), height: +box.height.toFixed(1) };
      const style = getComputedStyle(element);
      const standalone = element.tagName !== 'A' || style.display !== 'inline'
        || element.closest('.page-sections,.league-menu,.landing-actions,.landing-races,.landing-sport,.hub-finished,.caption-actions,.reel-slide-card');
      (standalone ? smallTargets : inlineLinks).push(item);
    }
    const viewport = innerWidth;
    const pageWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
    const overflow = pageWidth > viewport + 1;
    const overflowElements = overflow ? [...document.querySelectorAll('body *')].filter((element) => {
      if (!visible(element)) return false;
      const box = element.getBoundingClientRect();
      if (box.left >= -1 && box.right <= viewport + 1) return false;
      for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(parent).overflowX)) return false;
      }
      return true;
    }).slice(0, 12).map(describe) : [];
    return { viewport, pageWidth, overflow, overflowElements, smallText, smallTargets, inlineLinks,
      title: document.title, heading: document.querySelector('main h1')?.textContent.trim(),
      theme: document.documentElement.dataset.theme, reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      tables: document.querySelectorAll('main table').length };
  });
}

async function interactionAudit(page, family, record) {
  const check = async (name, action) => {
    try { const details = await action(); record.interactions.push({ name, passed: true, ...details }); }
    catch (error) { record.interactions.push({ name, passed: false, error: error.message.split('\n')[0] }); }
  };
  if (['football', 'cricket', 'f1'].includes(family)) {
    await check('section click retains league and deployment base', async () => {
      const link = page.locator('.page-sections a').first();
      if (!await link.count()) throw new Error('No section link rendered');
      const before = new URL(page.url());
      const href = await link.getAttribute('href');
      await link.click({ timeout: 4000 });
      const after = new URL(page.url());
      if (after.searchParams.get('league') !== before.searchParams.get('league') || !after.pathname.startsWith(base.pathname)) {
        throw new Error(`Section link lost league/base: ${href} -> ${after.href}`);
      }
      if (!after.hash) throw new Error(`Section link did not set a fragment: ${href}`);
      return { href, result: after.href };
    });
  }
  if (['football', 'cricket'].includes(family)) {
    await check('team row click retains league and writes team hash', async () => {
      const buttons = page.locator('main table .team-button');
      if (!await buttons.count()) throw new Error('No table team buttons rendered');
      const button = buttons.nth(Math.min(1, await buttons.count() - 1));
      const before = new URL(page.url());
      await button.click({ timeout: 4000 });
      const after = new URL(page.url());
      if (!after.hash.startsWith('#team=') || after.search !== before.search || !after.pathname.startsWith(base.pathname)) {
        throw new Error(`Team selection lost its league/base/hash: ${after.href}`);
      }
      if (await button.getAttribute('aria-pressed') !== 'true') throw new Error('Selected team button is not aria-pressed=true');
      return { result: after.href, selected: (await button.innerText()).trim() };
    });
  }
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  await check('league search filters and empty state; Escape restores focus', async () => {
    const trigger = page.locator('.league-menu-button');
    await trigger.click({ timeout: 4000 });
    const search = page.locator('.league-menu-panel input[type=search]');
    if (!await search.count()) throw new Error('League menu has no search input');
    record.menuSmallTargets = await page.locator('.league-menu-panel a,.league-menu-panel input').evaluateAll((elements) => elements.map((element) => {
      const box = element.getBoundingClientRect();
      return { text: (element.getAttribute('aria-label') || element.textContent || element.getAttribute('placeholder') || '').trim().slice(0, 80),
        width: +box.width.toFixed(1), height: +box.height.toFixed(1) };
    }).filter(({ width, height }) => width > 1 && height > 1 && (width < 43.5 || height < 43.5)));
    await search.fill('Premier', { timeout: 4000 });
    const links = page.locator('.league-menu-group a');
    const matches = await links.allTextContents();
    if (!matches.length) throw new Error('Search Premier produced no links');
    await search.fill('zzzz-unmatched-league');
    if (await links.count()) throw new Error('Unmatched search still exposes league links');
    if (!await page.locator('.league-menu-empty,[role=status]').filter({ hasText: /no leagues|no match/i }).count()) {
      throw new Error('No visible no-results message');
    }
    await search.press('Escape');
    if (await trigger.getAttribute('aria-expanded') !== 'false') throw new Error('Escape did not close the menu');
    if (!await trigger.evaluate((element) => document.activeElement === element)) throw new Error('Escape did not restore trigger focus');
    return { matches: matches.map((text) => text.trim()) };
  });
  await check('theme choice survives reload', async () => {
    const previous = await page.locator('html').getAttribute('data-theme');
    const expected = previous === 'dark' ? 'light' : 'dark';
    await page.locator('.theme-toggle').click({ timeout: 4000 });
    const chosen = await page.evaluate(() => ({ attribute: document.documentElement.dataset.theme, stored: localStorage.getItem('pp-theme') }));
    if (chosen.attribute !== expected || chosen.stored !== expected) throw new Error(`Theme toggle did not persist ${expected}: ${JSON.stringify(chosen)}`);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 20000 });
    await settle(page);
    const restored = await page.locator('html').getAttribute('data-theme');
    if (restored !== expected) throw new Error(`Theme after reload was ${restored}, expected ${expected}`);
    return { previous, chosen: expected, restored };
  });
}

async function run() {
  if (widths.some((value) => !Number.isFinite(value) || value < 200)) throw new Error('Invalid VERIFY_WIDTHS');
  for (const family of families) if (!(family in definitions)) throw new Error(`Unknown family: ${family}`);
  await mkdir(output, { recursive: true });
  const playwright = loadPlaywright();
  const axePath = await findAxe();
  report.axe = { available: Boolean(axePath), path: axePath };
  const axeSource = axePath ? await readFile(axePath, 'utf8') : null;
  for (const engine of engines) {
    let browser;
    try {
      if (!playwright[engine]?.launch) throw new Error(`Unknown engine: ${engine}`);
      const executablePath = engine === 'webkit' ? process.env.WEBKIT_EXECUTABLE : undefined;
      browser = await playwright[engine].launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
    } catch (error) {
      report.cases.push({ engine, setupError: error.message, passed: false });
      continue;
    }
    try {
      for (const width of widths) for (const theme of ['light', 'dark']) for (const family of families) {
        const record = { engine, width, theme, family, url: new URL(definitions[family], base).href,
          consoleErrors: [], pageErrors: [], failedRequests: [], httpErrors: [], interactions: [], passed: false };
        report.cases.push(record);
        const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce' });
        await context.addInitScript((initialTheme) => {
          try { if (!localStorage.getItem('pp-theme')) localStorage.setItem('pp-theme', initialTheme); } catch { /* Storage can be blocked. */ }
        }, theme);
        const page = await context.newPage();
        page.setDefaultTimeout(5000);
        page.on('console', (message) => { if (message.type() === 'error') record.consoleErrors.push(message.text()); });
        page.on('pageerror', (error) => record.pageErrors.push(error.message));
        page.on('requestfailed', (request) => {
          const error = request.failure()?.errorText || 'unknown';
          if (!/aborted|cancelled|canceled/i.test(error)) record.failedRequests.push({ url: request.url(), error });
        });
        page.on('response', (response) => { if (response.status() >= 400) record.httpErrors.push({ url: response.url(), status: response.status() }); });
        try {
          await page.goto(record.url, { waitUntil: 'domcontentloaded', timeout: 25000 });
          await settle(page);
          record.dom = await domAudit(page);
          record.screenshot = path.join(output, `${engine}-${family}-${width}-${theme}.png`);
          await page.screenshot({ path: record.screenshot, fullPage: true, timeout: 20000 });
          if (axeSource) {
            try {
              await page.addScriptTag({ content: axeSource });
              record.axe = await page.evaluate(async () => {
                const results = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
                return { passes: results.passes.length, incomplete: results.incomplete.map(({ id, impact, nodes }) => ({ id, impact, count: nodes.length })),
                  violations: results.violations.map(({ id, impact, description, helpUrl, nodes }) => ({ id, impact, description, helpUrl,
                    nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) })) };
              });
            } catch (error) { record.axe = { error: error.message }; }
          }
          await interactionAudit(page, family, record);
          record.passed = !record.dom.overflow && !record.dom.smallText.length && !record.dom.smallTargets.length
            && record.dom.theme === theme && !record.pageErrors.length && !record.consoleErrors.length
            && !record.httpErrors.length && !record.failedRequests.length && record.interactions.every((item) => item.passed)
            && !record.menuSmallTargets?.length
            && (!record.axe || (!record.axe.error && !record.axe.violations.length));
        } catch (error) {
          record.error = error.message.split('\n').slice(0, 3).join(' ');
          try { await page.screenshot({ path: path.join(output, `${engine}-${family}-${width}-${theme}-error.png`), fullPage: true, timeout: 5000 }); } catch { /* Preserve the original failure. */ }
        } finally { await context.close(); }
        process.stdout.write(`${record.passed ? 'PASS' : 'FAIL'} ${engine} ${family} ${width} ${theme}${record.error ? `: ${record.error}` : ''}\n`);
        await writeFile(path.join(output, 'results.json'), `${JSON.stringify(report, null, 2)}\n`);
      }
    } finally { await browser.close(); }
  }
  report.completedAt = new Date().toISOString();
  report.summary = { cases: report.cases.length, passed: report.cases.filter((item) => item.passed).length,
    failed: report.cases.filter((item) => !item.passed).length,
    axeAvailable: Boolean(axePath), output };
  await writeFile(path.join(output, 'results.json'), `${JSON.stringify(report, null, 2)}\n`);
  process.stdout.write(`${JSON.stringify(report.summary)}\n`);
  process.exitCode = report.summary.failed ? 1 : 0;
}
run().catch(async (error) => {
  report.setupError = error.message;
  try { await mkdir(output, { recursive: true }); await writeFile(path.join(output, 'results.json'), `${JSON.stringify(report, null, 2)}\n`); } catch { /* Print setup failure even when output is unwritable. */ }
  process.stderr.write(`Verification setup failed: ${error.message}\n`);
  process.exitCode = 2;
});
