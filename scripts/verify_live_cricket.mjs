#!/usr/bin/env node
/**
 * Explicit Live Cricket browser contract checks; no provider credentials or raw payload artifacts.
 * PLAYWRIGHT_MODULE=/existing/playwright node scripts/verify_live_cricket.mjs BASE LABEL [--service]
 * Free mode makes one unmodified browser discovery/detail request, then shares those real responses
 * only in memory for the browser matrix. Service mode replays clearly synthetic normalized contracts.
 */
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const playwright = require(process.env.PLAYWRIGHT_MODULE || '/Users/Rakesh/gstack/node_modules/playwright');
const engineRuntime = engine => engine === 'webkit' && process.env.WEBKIT_PLAYWRIGHT_MODULE ? require(process.env.WEBKIT_PLAYWRIGHT_MODULE)[engine] : playwright[engine];
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const base = new URL(process.argv[2] || 'http://127.0.0.1:5193/ipl_top4_analysis/');
if (!base.pathname.endsWith('/')) base.pathname += '/';
base.search = ''; base.hash = '';
const label = (process.argv[3] || 'github').replace(/[^a-zA-Z0-9_-]/g, '-');
const parentScoreOnly = process.argv.includes('--parent-score-only');
const service = process.argv.includes('--service') || parentScoreOnly;
const engines = (process.env.LIVE_VERIFY_BROWSERS || 'chromium,webkit').split(',');
const widths = (process.env.LIVE_VERIFY_WIDTHS || '320,375,1280').split(',').map(Number);
const themes = (process.env.LIVE_VERIFY_THEMES || 'light,dark').split(',');
const output = path.join(root, 'docs/qa/live-cricket', label);
const report = { base: base.href, label, mode: parentScoreOnly ? 'synthetic-parent-score-followup' : service ? 'synthetic-service-contracts' : 'real-free-source-with-in-memory-replays', startedAt: new Date().toISOString(), providerProbe: null, cases: [], summary: {}, limitations: [
  'Only owned local build tabs and contexts were used. No subscriptions or credential-bearing requests.',
  'Provider payloads stay in memory; matrix contexts replay the same bounded real snapshot and do not establish ongoing provider availability.',
  'Synthetic contracts are test-only browser network responses, not real matches, predictions or bookmaker prices.',
  'Computed contrast includes alpha blending over opaque UI planes; ambient/gradient page backgrounds and disabled controls are excluded.',
  'No manual screen-reader assessment, Lighthouse run or real-user INP measurement is claimed.'
] };
report.runtime = { playwright: process.env.PLAYWRIGHT_MODULE || '/Users/Rakesh/gstack/node_modules/playwright', webkitPlaywright: process.env.WEBKIT_PLAYWRIGHT_MODULE ?? null, webkitExecutable: process.env.WEBKIT_EXECUTABLE ?? null };
report.configuration = { engines, widths, themes };
const sourceCache = new Map();
let selectedId, selectedSlug;
const launchOptions = engine => ({ headless: true, timeout: 20000, ...(engine === 'webkit' && process.env.WEBKIT_EXECUTABLE ? { executablePath: process.env.WEBKIT_EXECUTABLE } : {}) });

function must(condition, message) { if (!condition) throw new Error(message); }
async function keyboardActivate(page, name) {
  const button = page.getByRole('button', { name, exact: true });
  await button.focus(); await button.press('Enter');
}
async function step(record, name, action) {
  try { record.checks.push({ name, passed: true, ...(await action() || {}) }); }
  catch (error) { record.checks.push({ name, passed: false, error: error.message.split('\n')[0] }); }
}
async function settle(page) {
  await page.locator('main h1').waitFor({ state: 'visible' });
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function audit(page) {
  return page.evaluate(() => {
    const desc = el => ({ tag: el.tagName.toLowerCase(), text: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 80), class: typeof el.className === 'string' ? el.className : '' });
    const visible = el => { const b = el.getBoundingClientRect(), s = getComputedStyle(el); return b.width > 1 && b.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('.visually-hidden,[hidden]') && !(s.clip && s.clip !== 'auto'); };
    const smallText = [...document.querySelectorAll('body *')].filter(el => visible(el) && [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim()) && parseFloat(getComputedStyle(el).fontSize) < 11.99).map(el => ({ ...desc(el), fontSize: getComputedStyle(el).fontSize }));
    const smallTargets = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=tab]')].filter(el => visible(el) && !el.matches('.skip-link,[disabled]') && !(el.tagName === 'A' && getComputedStyle(el).display === 'inline')).flatMap(el => { const b = el.getBoundingClientRect(); return b.width < 43.5 || b.height < 43.5 ? [{ ...desc(el), width: b.width, height: b.height }] : []; });
    const rgba = value => { const match = /^rgba?\(([^)]+)\)/.exec(value); if (!match) return null; const parts = match[1].split(/[,\s/]+/).filter(Boolean).map(Number); return [parts[0], parts[1], parts[2], parts[3] ?? 1]; };
    const blend = (front, back) => front.slice(0, 3).map((c, i) => c * front[3] + back[i] * (1 - front[3]));
    const luminance = rgb => rgb.map(c => { const v = c / 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }).reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
    const contrast = [], skippedContrast = [];
    for (const el of document.querySelectorAll('.lc-center *,.lc-status-filters button,.lc-search input,.lc-field select,.lc-button,.lc-match-link[aria-current]')) {
      if (!visible(el) || el.closest('[disabled]') || ![...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim())) continue;
      const layers = []; let opaque = false, unsafe = false;
      for (let current = el; current; current = current.parentElement) {
        const style = getComputedStyle(current), color = rgba(style.backgroundColor);
        if (style.backgroundImage !== 'none' || Number(style.opacity) < 1) { unsafe = true; break; }
        if (color) layers.push(color);
        if (color?.[3] === 1) { opaque = true; break; }
        if (current === document.body) break;
      }
      if (!opaque || unsafe) { skippedContrast.push(desc(el)); continue; }
      let bg = layers.pop().slice(0, 3);
      while (layers.length) bg = blend(layers.pop(), bg);
      const style = getComputedStyle(el), fgValue = rgba(style.color);
      if (!fgValue) continue;
      const fg = blend(fgValue, bg), a = luminance(fg), b = luminance(bg), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
      const size = parseFloat(style.fontSize), large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700), minimum = large ? 3 : 4.5;
      contrast.push({ ...desc(el), ratio: +ratio.toFixed(3), minimum, passed: ratio + .005 >= minimum, foreground: fg, background: bg });
    }
    return { viewport: innerWidth, pageWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth), overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth + 1, smallText, smallTargets, contrast, skippedContrast: skippedContrast.length, reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches };
  });
}
async function capture(page, record, name) {
  const file = `${record.engine}-${record.width}-${record.theme}-${name}.png`;
  if (name.endsWith('lobby')) await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
  else if (await page.locator('.lc-panel').count()) await page.locator('.lc-panel').evaluate(el => el.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  // Viewport captures preserve a truthful sticky-header position. Element captures
  // taller than the viewport can paint a sticky header halfway through the target.
  await page.screenshot({ path: path.join(output, file), fullPage: false });
  record.screenshots.push(file);
}
async function probeProvider() {
  const browser = await playwright.chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'dark' });
  const page = await context.newPage(), pending = [], requests = [], errors = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (!response.url().startsWith('https://sportscore.com/api/widget/')) return;
    pending.push((async () => {
      const body = await response.body(), headers = await response.allHeaders();
      delete headers['content-length']; delete headers['content-encoding'];
      sourceCache.set(response.url(), { status: response.status(), headers, body });
      requests.push({ url: response.url(), status: response.status(), bytes: body.length, accessControlAllowOrigin: headers['access-control-allow-origin'] ?? null });
    })());
  });
  try {
    await page.goto(new URL('cricket/', base).href, { waitUntil: 'domcontentloaded' });
    await page.locator('.lc-update-status').filter({ hasText: /Automatic checks/ }).waitFor({ timeout: 20000 });
    await page.getByRole('button', { name: 'All', exact: true }).click();
    await page.locator('.lc-match-link').first().waitFor();
    const href = await page.locator('.lc-match-link').last().getAttribute('href');
    selectedId = new URL(href, base).searchParams.get('match');
    must(selectedId, 'Real provider list produced no usable public match ID');
    await page.locator('.lc-match-link').last().click();
    await page.getByRole('tab', { name: 'Scorecard', exact: true }).click();
    await page.getByRole('heading', { name: 'Scorecard not supplied', exact: true }).waitFor({ timeout: 20000 });
    await Promise.all(pending);
    selectedSlug = [...sourceCache.keys()].find(url => new URL(url).pathname.endsWith('/match/'));
    must(selectedSlug, 'No actual provider match drilldown response was captured');
    report.providerProbe = { passed: !errors.length && requests.every(r => r.status === 200), capturedAt: new Date().toISOString(), coveredMatches: await page.locator('.lc-match-link').count(), selectedId, requests, errors, note: 'Unmodified built page; direct browser CORS requests, no interception during this probe.' };
    must(report.providerProbe.passed, 'Unmodified provider/CORS probe failed');
  } finally { await context.close(); await browser.close(); }
}
async function freeMatrix() {
  await probeProvider();
  for (const engine of engines) {
    const browser = await engineRuntime(engine).launch(launchOptions(engine));
    try { for (const width of widths) for (const theme of themes) {
      const record = { engine, width, theme, source: 'unchanged real snapshot replayed in memory', checks: [], errors: [], screenshots: [], passed: false }; report.cases.push(record);
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: width === 320 ? 'reduce' : 'no-preference' });
      await context.addInitScript(initial => { try { if (!localStorage.getItem('pp-theme')) localStorage.setItem('pp-theme', initial); } catch { /* origin storage not yet available */ } }, theme);
      let providerAttempts = 0;
      await context.route('https://sportscore.com/api/widget/**', async route => { providerAttempts++; const cached = sourceCache.get(route.request().url()); if (cached) await route.fulfill(cached); else await route.abort('blockedbyclient'); });
      const page = await context.newPage(); page.setDefaultTimeout(7000);
      page.on('console', message => { if (message.type() === 'error') record.errors.push(message.text()); });
      page.on('pageerror', error => record.errors.push(error.message));
      try {
        await page.goto(new URL('cricket/', base).href, { waitUntil: 'domcontentloaded' }); await settle(page);
        await page.getByRole('button', { name: 'All', exact: true }).click(); await page.locator('.lc-match-link').first().waitFor();
        await step(record, 'bounded real-source lobby, attribution and field-level coverage', async () => {
          must(await page.locator('.lc-match-link').count() > 0, 'No provider matches');
          must(await page.locator('.lc-attribution').isVisible(), 'Missing required attribution');
          const coverage = await page.locator('.lc-coverage').innerText(); must(/not a complete worldwide/i.test(coverage), 'Missing worldwide coverage qualifier');
          return { matches: await page.locator('.lc-match-link').count() };
        });
        if (engine === 'chromium' && width !== 320) await capture(page, record, 'real-lobby');
        await step(record, 'a lower fixture brings the selected score and keyboard focus into view; Back focuses the lobby', async () => {
          const link = page.locator(`.lc-match-link[href*="${selectedId}"]`); await link.scrollIntoViewIfNeeded();
          const before = await page.evaluate(() => scrollY); await link.click();
          await page.waitForFunction(() => document.activeElement?.id === 'lc-match-heading');
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          const heading = await page.locator('#lc-match-heading').boundingBox();
          const header = await page.locator('.site-header').boundingBox();
          must(heading && heading.y >= 0 && heading.y < 900, `Selected match heading remains outside viewport: ${JSON.stringify(heading)}`);
          must(!header || heading.y >= header.y + header.height - 1, `Selected match heading is covered by the sticky header: ${JSON.stringify({ heading, header })}`);
          await page.goBack(); await page.waitForFunction(() => document.activeElement?.id === 'lc-lobby-heading');
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          const lobby = await page.locator('#lc-lobby-heading').boundingBox();
          must(lobby && lobby.y >= 0 && lobby.y < 900, `Back left lobby heading outside viewport: ${JSON.stringify(lobby)}`);
          const backHeader = await page.locator('.site-header').boundingBox();
          must(!backHeader || lobby.y >= backHeader.y + backHeader.height - 1, `Lobby heading is covered by the sticky header: ${JSON.stringify({ lobby, header: backHeader })}`);
          return { scrollBefore: before, selectedHeadingTop: heading.y, lobbyHeadingTop: lobby.y };
        });
        await step(record, 'search, drilldown, Back and selected deep-link reload retain deployment base', async () => {
          const link = page.locator(`.lc-match-link[href*="${selectedId}"]`); const title = (await link.locator(':scope > strong').innerText()).split(' v ')[0];
          await page.getByRole('searchbox', { name: 'Search teams, competition or venue' }).fill(title);
          await link.click(); must(new URL(page.url()).pathname === new URL('cricket/', base).pathname, 'Drilldown lost deployment base');
          await page.locator('.lc-center').waitFor(); const deep = page.url();
          await page.goBack(); must(!new URL(page.url()).searchParams.has('match'), 'Back did not return to lobby');
          must(await page.getByRole('searchbox', { name: 'Search teams, competition or venue' }).inputValue() === title, 'Back lost lobby filters');
          await page.locator(`.lc-match-link[href*="${selectedId}"]`).click(); await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator('.lc-center').waitFor();
          must(page.url() === deep, 'Reload lost selected match'); return { deepLink: deep, filter: title };
        });
        await step(record, 'direct bookmark metadata and source links retain the correct hosting base', async () => {
          const metadata = await page.evaluate(() => ({ canonical: document.querySelector('link[rel=canonical]')?.href, ogUrl: document.querySelector('meta[property="og:url"]')?.content, description: document.querySelector('meta[name=description]')?.content, activeRoute: document.querySelector('a[aria-current=page]')?.getAttribute('href'), attribution: document.querySelector('.lc-attribution')?.href }));
          const wantedPath = new URL('cricket/', base).pathname;
          must(metadata.canonical && new URL(metadata.canonical).pathname === wantedPath, `Canonical path ${metadata.canonical} does not match ${wantedPath}`);
          must(metadata.ogUrl && new URL(metadata.ogUrl).pathname === wantedPath, `Open Graph URL path mismatch: ${metadata.ogUrl}`);
          must(metadata.description?.length > 20, 'Meaningful route description absent');
          must(metadata.attribution === 'https://sportscore.com/', 'Provider attribution destination incorrect');
          return metadata;
        });
        await step(record, 'roving tabs support arrows, Home and End', async () => {
          const summary = page.getByRole('tab', { name: 'Summary', exact: true }); await summary.focus(); await summary.press('ArrowRight');
          must(await page.getByRole('tab', { name: 'Scorecard', exact: true }).getAttribute('aria-selected') === 'true', 'ArrowRight did not select Scorecard');
          await page.keyboard.press('End'); must(await page.getByRole('tab', { name: 'Field guide', exact: true }).getAttribute('aria-selected') === 'true', 'End did not select Field guide');
          await page.keyboard.press('Home'); must(await summary.getAttribute('aria-selected') === 'true', 'Home did not select Summary');
          must(await summary.evaluate(el => document.activeElement === el), 'Roving tab focus not restored');
        });
        for (const [tab, heading] of [['Scorecard', /Scorecard not supplied/i], ['Commentary', /Ball-by-ball commentary not supplied/i], ['Model win chance', /Match win model not available/i], ['Bookmaker odds', /Bookmaker prices not supplied/i]]) await step(record, `real ${tab} is honestly unavailable`, async () => {
          await page.getByRole('tab', { name: tab, exact: true }).click(); await page.getByRole('heading', { name: heading }).waitFor();
          must(await page.locator('.lc-probabilities,.lc-price-list').count() === 0, 'Unsupported prediction or price appeared');
          if (engine === 'chromium' && width === 1280 && theme === 'dark' && /Model|Bookmaker/.test(tab)) await capture(page, record, `real-${tab.startsWith('Model') ? 'model' : 'markets'}-unavailable`);
        });
        await step(record, 'pause freezes foreground requests and Resume preserves selected match and focus', async () => {
          await page.clock.install(); await keyboardActivate(page, 'Pause updates');
          const before = providerAttempts, href = page.url(); await page.clock.fastForward(90_000); await page.waitForTimeout(60);
          must(providerAttempts === before, 'A provider request occurred while paused');
          must(await page.locator('.lc-update-status').innerText().then(text => /Updates paused at/.test(text)), 'Paused timestamp not visible');
          await keyboardActivate(page, 'Resume updates');
          await page.waitForFunction(() => !document.querySelector('.lc-update-status').textContent.includes('Updates paused'));
          must(page.url() === href, 'Resume lost selection');
          must(await page.getByRole('button', { name: 'Pause updates', exact: true }).evaluate(el => document.activeElement === el), 'Resume lost keyboard focus');
          return { requestsDuringPause: 0, selected: href };
        });
        await step(record, 'optional field guide defaults flat; tilt is explicit and reduced-motion-safe', async () => {
          await page.getByRole('tab', { name: 'Field guide', exact: true }).click(); await page.locator('.lc-field-svg').waitFor();
          must(!await page.locator('.lc-field-svg').evaluate(el => el.classList.contains('is-tilted')), 'Field was tilted automatically');
          if (width === 320) { must(await page.getByRole('button', { name: 'Tilt field' }).isDisabled(), 'Reduced motion did not disable tilt'); }
          else { await page.getByRole('button', { name: 'Tilt field' }).click(); must(await page.locator('.lc-field-svg').evaluate(el => el.classList.contains('is-tilted')), 'Explicit tilt did not change field'); }
          must(await page.locator('.lc-guide-legend').innerText().then(text => /Bowler/.test(text) && /Wicketkeeper/.test(text)), 'Text equivalent missing');
          if (engine === 'chromium' && width !== 320) await capture(page, record, 'real-field-guide');
        });
        record.audit = await audit(page);
        await step(record, 'phone/desktop geometry, 44px controls, 12px text and solid-plane composited contrast', async () => {
          must(!record.audit.overflow, `Page overflow ${record.audit.pageWidth}/${width}`);
          must(!record.audit.smallTargets.length, `Small targets: ${JSON.stringify(record.audit.smallTargets)}`);
          must(!record.audit.smallText.length, `Small text: ${JSON.stringify(record.audit.smallText)}`);
          must(!record.audit.contrast.some(sample => !sample.passed), `Contrast failures: ${JSON.stringify(record.audit.contrast.filter(sample => !sample.passed))}`);
          return { contrastSamples: record.audit.contrast.length };
        });
        await step(record, 'theme selection persists across reload', async () => {
          const next = theme === 'light' ? 'dark' : 'light'; await page.locator('.theme-toggle').click();
          must(await page.evaluate(() => localStorage.getItem('pp-theme')) === next, 'Theme preference not stored');
          await page.reload({ waitUntil: 'domcontentloaded' }); await settle(page);
          must(await page.locator('html').getAttribute('data-theme') === next, 'Theme not restored');
        });
      } catch (error) { record.checks.push({ name: 'case setup/execution', passed: false, error: error.message.split('\n')[0] }); }
      finally { record.providerReplayRequests = providerAttempts; record.passed = !record.errors.length && record.checks.every(check => check.passed); await context.close(); }
      process.stdout.write(`${record.passed ? 'PASS' : 'FAIL'} ${engine} ${width} ${theme}\n`);
    } } finally { await browser.close(); }
  }
}

// Synthetic normalized service contracts are deliberately named and never imported by production.
function fixture(now, { quoteAge = 0, scoreAge = 0, publicationAge = 0, scoreObservedMissing = false, modelAge = 0, modelRevision = 'score-one', marketState = 'open', state = 'live' } = {}) {
  const instant = new Date(now).toISOString(), ago = seconds => new Date(now - seconds * 1000).toISOString();
  const source = { id: 'synthetic-browser-test', name: 'Synthetic browser contract fixture', url: 'https://example.test/' };
  const match = { id: 'synthetic-browser-one', providerIds: {}, teams: [{ id: 'a', name: 'Synthetic Alpha', shortName: 'ALP' }, { id: 'b', name: 'Synthetic Beta', shortName: 'BET' }], competition: { id: 'synthetic-t20', name: 'Synthetic women’s T20 test' }, format: 'T20', gender: 'female', state, statusText: 'Synthetic test innings in progress', startTime: ago(3600), venue: 'Synthetic test ground', scores: [{ id: 'i1', team: 'Synthetic Alpha', label: 'First innings', runs: 100, wickets: 2, legalBalls: 72, overs: '12.0' }], observedAt: scoreObservedMissing ? null : ago(scoreAge), fetchedAt: instant, revision: 'score-one', capabilities: { scorecard: true, commentary: true, model: true, markets: true }, source };
  const meta = { schemaVersion: 1, status: 'ok', message: 'Synthetic browser-only contract replay; never a real match.', source, generatedAt: ago(publicationAge), refreshAfterSeconds: 5, staleAfterSeconds: 90 };
  const part = data => ({ status: 'available', source: source.name, observedAt: instant, fetchedAt: instant, reason: null, data });
  const list = { ...meta, matches: [match], coverage: [{ competition: match.competition.name, scores: true, scorecard: true, commentary: true, markets: true, note: 'Synthetic test coverage' }] };
  const model = { modelId: 'synthetic-test-only', modelVersion: 'test-version', scoreRevision: modelRevision, predictedAt: ago(modelAge), conditioning: 'Synthetic test, conditional on completion.', probabilities: [{ outcome: 'Synthetic Alpha', probability: .61 }, { outcome: 'Synthetic Beta', probability: .39 }], history: [] };
  const markets = [{ key: 'synthetic-book', title: 'Synthetic test bookmaker', updatedAt: ago(quoteAge), markets: [{ key: 'h2h', name: 'Synthetic match winner', state: marketState, updatedAt: ago(quoteAge), settlement: 'Synthetic outcome including super over; test only.', outcomes: [{ name: 'Synthetic Alpha', price: 1.75 }, { name: 'Synthetic Beta', price: 2.1 }] }] }];
  const innings = { ...match.scores[0], batting: [{ id: 'batter-one', name: 'Synthetic Batter With A Deliberately Long Name', dismissal: 'not out', runs: 55, balls: 35, fours: 4, sixes: 2, strikeRate: 157.14 }], bowling: [{ id: 'bowler-one', name: 'Synthetic Bowler With A Deliberately Long Name', overs: '4.0', maidens: 0, runs: 30, wickets: 1, economy: 7.5 }], extras: '5 wides', fallOfWickets: ['1–20'], partnerships: ['30 runs'] };
  const commentary = [{ id: 'delivery-one', sequence: 1, innings: 'i1', over: '11.6', batter: 'Synthetic Batter', bowler: 'Synthetic Bowler', runs: 4, extras: 0, wickets: 0, text: 'Synthetic commentary fixture, not a real delivery.', observedAt: instant, revision: 'one' }];
  return { list, detail: { ...meta, match, scorecard: part([innings]), commentary: part(commentary), model: part(model), markets: part(markets) } };
}
async function parentScoreChecks(page, record, setMode) {
  await step(record, 'fresh parent score and fresh same-revision model establish a visible baseline', async () => {
    setMode('fresh'); await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
    await page.getByRole('tab', { name: 'Model win chance', exact: true }).click();
    await page.locator('.lc-probabilities').waitFor();
    must(/61/.test(await page.locator('.lc-probabilities').innerText()), 'Fresh synthetic baseline estimate did not appear');
  });
  for (const [mode, name, ages] of [
    ['old-score', 'a freshly calculated same-revision model is withheld for an overdue parent observedAt', { scoreObservedAgeSeconds: 600, publicationAgeSeconds: 0, predictionAgeSeconds: 0, outerModelObservedAgeSeconds: 0 }],
    ['old-score-publication', 'absent parent observedAt uses overdue generatedAt rather than fresh fetch or prediction clocks', { scoreObservedAt: null, publicationAgeSeconds: 600, predictionAgeSeconds: 0, outerModelObservedAgeSeconds: 0 }]
  ]) await step(record, name, async () => {
    setMode(mode); await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
    if (mode === 'old-score-publication') await page.locator('.lc-match-header .lc-clocks').getByText('Event time not supplied', { exact: true }).waitFor();
    await page.getByRole('heading', { name: 'Current model estimate unavailable', exact: true }).waitFor();
    await page.getByText('The parent score source is overdue. Waiting for a fresh score snapshot before showing a current estimate.', { exact: true }).waitFor();
    must(!await page.locator('.lc-probabilities').count(), 'Fresh prediction over an overdue parent score remained visible');
    if (parentScoreOnly) await capture(page, record, `synthetic-${mode}-model-withheld`);
    return { syntheticClockContract: ages, matchingScoreRevision: 'score-one' };
  });
  await step(record, 'fresh parent score recovery restores the matching estimate without changing selection', async () => {
    const before = page.url(); setMode('fresh'); await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
    await page.locator('.lc-probabilities').waitFor(); must(page.url() === before, 'Parent-score recovery lost selected match');
  });
}
async function serviceMatrix() {
  for (const engine of engines) {
    const browser = await engineRuntime(engine).launch(launchOptions(engine));
    try { for (const width of widths) for (const theme of themes) {
      const record = { engine, width, theme, source: 'synthetic normalized service contracts', checks: [], errors: [], screenshots: [], passed: false }; report.cases.push(record);
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce' });
      await context.addInitScript(initial => { try { localStorage.setItem('pp-theme', initial); } catch { /* no storage for initial blank origin */ } }, theme);
      let mode = 'fresh', calls = 0, syntheticClockOffset = 0;
      await context.route('**/v1/matches**', async route => {
        calls++;
        if (mode === 'outage') return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"synthetic outage"}' });
        const state = fixture(Date.now() + syntheticClockOffset, mode === 'old-quotes' ? { quoteAge: 600 } : mode === 'old-score' ? { scoreAge: 600 } : mode === 'old-score-publication' ? { publicationAge: 600, scoreObservedMissing: true } : mode === 'old-model' ? { modelAge: 600 } : mode === 'suspended-market' ? { marketState: 'suspended' } : mode === 'revision-mismatch' ? { modelRevision: 'wrong-revision' } : {});
        return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(new URL(route.request().url()).pathname === '/v1/matches' ? state.list : state.detail) });
      });
      const page = await context.newPage(); page.setDefaultTimeout(7000);
      page.on('console', message => { if (message.type() === 'error' && !message.text().includes('503')) record.errors.push(message.text()); });
      page.on('pageerror', error => record.errors.push(error.message));
      try {
        await page.goto(new URL('cricket/?match=synthetic-browser-one', base).href, { waitUntil: 'domcontentloaded' }); await settle(page); await page.locator('.lc-center').waitFor();
        if (parentScoreOnly) {
          await parentScoreChecks(page, record, value => { mode = value; });
        } else {
        await step(record, 'synthetic full scorecard is a contained, labelled table at every viewport', async () => {
          await page.getByRole('tab', { name: 'Scorecard', exact: true }).click(); await page.locator('.lc-table-wrap table').first().waitFor();
          const tableAudit = await audit(page); must(!tableAudit.overflow, `Scorecard page overflow ${tableAudit.pageWidth}/${width}`);
          must(await page.locator('.lc-table-wrap caption').count() > 0, 'Table captions absent');
          must(await page.locator('.lc-table-wrap th[scope]').count() > 0, 'Scoped table headers absent');
          if (engine === 'chromium' && width !== 320) await capture(page, record, 'synthetic-scorecard');
        });
        await step(record, 'synthetic model is separate and tied to the accepted score revision', async () => {
          await page.getByRole('tab', { name: 'Model win chance', exact: true }).click(); await page.locator('.lc-probabilities').waitFor();
          must(/61/.test(await page.locator('.lc-probabilities').innerText()), 'Synthetic expected model percent not rendered');
          must(!await page.locator('.lc-price-list').count(), 'Bookmaker prices mixed into model panel');
        });
        await step(record, 'fresh synthetic market is current; pausing immediately removes current status', async () => {
          await page.getByRole('tab', { name: 'Bookmaker odds', exact: true }).click(); await page.getByText('Current quote', { exact: true }).first().waitFor();
          await page.clock.install(); await keyboardActivate(page, 'Pause updates'); const before = calls;
          must(!await page.getByText('Current quote', { exact: true }).count(), 'Paused quote remained current');
          must(await page.getByText('Last quoted price · not current', { exact: true }).count() === 2, 'Paused quote qualifier absent');
          syntheticClockOffset += 120_000; await page.clock.fastForward(120_000); await page.waitForTimeout(60); must(calls === before, 'Paused client still polled');
          if (engine === 'chromium' && width === 1280 && theme === 'dark') await capture(page, record, 'synthetic-paused-market');
          await keyboardActivate(page, 'Resume updates'); await page.getByText('Current quote', { exact: true }).first().waitFor();
        });
        await step(record, 'fresh collection time does not refresh old quote source time', async () => {
          mode = 'old-quotes';
          await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.getByText('Last quote · open · overdue', { exact: true }).waitFor(); must(!await page.getByText('Current quote', { exact: true }).count(), 'Old quote appeared current');
        });
        await step(record, 'score and market clocks remain independent', async () => {
          mode = 'old-score'; await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.getByText('Score source overdue · displaying the last known score.', { exact: true }).waitFor(); await page.getByText('Current quote', { exact: true }).first().waitFor();
          if (engine === 'chromium' && width === 1280 && theme === 'dark') await capture(page, record, 'synthetic-independent-clocks');
        });
        await parentScoreChecks(page, record, value => { mode = value; });
        await step(record, 'suspended synthetic markets cannot appear current', async () => {
          mode = 'suspended-market'; await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.locator('.lc-market-heading .lc-state').filter({ hasText: 'Suspended' }).waitFor();
          must(!await page.getByText('Current quote', { exact: true }).count(), 'Suspended quote remained current');
        });
        await step(record, 'old model prediction time is withheld even when its score revision matches', async () => {
          mode = 'old-model'; await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.getByRole('tab', { name: 'Model win chance', exact: true }).click(); await page.getByRole('heading', { name: /Current model estimate unavailable/i }).waitFor(); must(!await page.locator('.lc-probabilities').count(), 'Overdue model remained visible');
        });
        await step(record, 'model revision mismatch suppresses probabilities', async () => {
          mode = 'revision-mismatch'; await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.getByRole('tab', { name: 'Model win chance', exact: true }).click(); await page.getByRole('heading', { name: /Current model estimate unavailable/i }).waitFor();
          await page.getByText('The model uses an earlier score revision. Waiting for a matching calculation.', { exact: true }).waitFor();
          must(!await page.locator('.lc-probabilities').count(), 'Mismatched revision model remained visible');
        });
        await step(record, 'outage retains last accepted match and exposes recovery without completing the match', async () => {
          mode = 'outage'; await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.locator('.lc-update-status').filter({ hasText: /Connection interrupted/ }).waitFor();
          must(await page.locator('.lc-center').count() === 1, 'Outage removed accepted match'); must((await page.locator('.lc-match-meta .lc-state').innerText()) === 'Live', 'Outage changed the accepted match state');
          must(await page.getByRole('button', { name: 'Try again', exact: true }).isVisible(), 'No recovery control');
          await page.getByRole('tab', { name: 'Bookmaker odds', exact: true }).click();
          must(!await page.getByText('Current quote', { exact: true }).count(), 'Feed outage left retained bookmaker quotes labelled current');
          if (engine === 'chromium' && width !== 320) await capture(page, record, 'synthetic-outage');
        });
        await step(record, 'recovery accepts a new snapshot in place without losing selection or focus', async () => {
          mode = 'fresh'; const before = page.url(); await keyboardActivate(page, 'Pause updates'); await keyboardActivate(page, 'Resume updates');
          await page.getByText('Current quote', { exact: true }).first().waitFor(); must(page.url() === before, 'Recovery lost selected match');
          must(await page.getByRole('button', { name: 'Pause updates', exact: true }).evaluate(el => document.activeElement === el), 'Recovery moved focus');
        });
        record.audit = await audit(page);
        await step(record, 'synthetic states retain geometry, targets, text and contrast', async () => {
          must(!record.audit.overflow, `Page overflow ${record.audit.pageWidth}/${width}`); must(!record.audit.smallText.length, 'Small text'); must(!record.audit.smallTargets.length, 'Small controls'); must(!record.audit.contrast.some(sample => !sample.passed), 'Contrast failure');
        });
        }
      } catch (error) { record.checks.push({ name: 'case setup/execution', passed: false, error: error.message.split('\n')[0] }); }
      finally { record.requests = calls; record.passed = !record.errors.length && record.checks.every(check => check.passed); await context.close(); }
      process.stdout.write(`${record.passed ? 'PASS' : 'FAIL'} ${engine} ${width} ${theme}\n`);
    } } finally { await browser.close(); }
  }
}
await mkdir(output, { recursive: true });
try { if (service) await serviceMatrix(); else await freeMatrix(); }
catch (error) { report.setupError = error.stack; }
report.completedAt = new Date().toISOString();
report.summary = { total: report.cases.length, passed: report.cases.filter(c => c.passed).length, failed: report.cases.filter(c => !c.passed).length, checks: report.cases.reduce((sum, c) => sum + c.checks.length, 0), contrastSamples: report.cases.reduce((sum, c) => sum + (c.audit?.contrast.length ?? 0), 0), providerNetworkRequests: report.providerProbe?.requests.length ?? 0 };
await writeFile(path.join(output, 'results.json'), `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(report.summary)}\n`);
if (report.setupError || report.summary.failed || !report.summary.total) process.exitCode = 1;
