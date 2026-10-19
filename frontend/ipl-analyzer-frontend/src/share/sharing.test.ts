import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mockPayload } from '../test/fixtures';
import { exportRacePng, raceCaption, shareTexts } from './sharing';

type Point = [number, number];

function captureCanvas() {
  let path: Point[] = [];
  const fills: Array<{ color: string; points: Point[] }> = [];
  const texts: Array<{ value: string; font: string }> = [];
  const context = {
    fillStyle: '', strokeStyle: '', lineWidth: 0, font: '',
    beginPath() { path = []; },
    moveTo(x: number, y: number) { path.push([x, y]); },
    lineTo(x: number, y: number) { path.push([x, y]); },
    quadraticCurveTo(cx: number, cy: number, x: number, y: number) { path.push([cx, cy], [x, y]); },
    closePath() {},
    fill() { fills.push({ color: this.fillStyle, points: [...path] }); },
    stroke() {},
    fillRect() {},
    fillText(value: string) { texts.push({ value, font: this.font }); },
    createLinearGradient() { return { addColorStop() {} }; },
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback) => callback(new Blob(['png'], { type: 'image/png' })));
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

  // Include curve control points: an excessive corner radius can extend a tiny bar.
  const rowTracks = (index: number) => fills
    .map(({ points }) => ({
      left: Math.min(...points.map(([x]) => x)),
      right: Math.max(...points.map(([x]) => x)),
      top: Math.min(...points.map(([, y]) => y)),
      bottom: Math.max(...points.map(([, y]) => y)),
    }))
    .filter(({ top, bottom }) => top === 324 + index * 78 && bottom === 342 + index * 78);

  return { rowTracks, texts };
}

describe('share probability exports', () => {
  const originalFonts = Object.getOwnPropertyDescriptor(document, 'fonts');

  beforeEach(() => {
    const OriginalURL = URL;
    vi.stubGlobal('URL', class extends OriginalURL {
      static createObjectURL = vi.fn(() => 'blob:race');
      static revokeObjectURL = vi.fn();
    });
    Object.defineProperty(document, 'fonts', {
      configurable: true,
      value: { ready: Promise.resolve(), load: vi.fn().mockResolvedValue([]) },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    if (originalFonts) Object.defineProperty(document, 'fonts', originalFonts);
    else Reflect.deleteProperty(document, 'fonts');
  });

  it('paints only the empty track for a zero-probability team', async () => {
    const canvas = captureCanvas();
    const payload = structuredClone(mockPayload);
    payload.analysis.overallProbabilities.Punjab.top4 = 0;

    await exportRacePng(payload);

    expect(canvas.rowTracks(0)).toEqual([{ left: 620, right: 840, top: 324, bottom: 342 }]);
  });

  it('keeps a tiny probability within its exact share of the 220px track', async () => {
    const canvas = captureCanvas();
    const payload = structuredClone(mockPayload);
    payload.analysis.overallProbabilities.Punjab.top4 = 0.1;

    await exportRacePng(payload);

    const tracks = canvas.rowTracks(0);
    expect(tracks).toHaveLength(2);
    expect(tracks[1].right - tracks[1].left).toBeCloseTo(220 * 0.1 / 100, 8);
  });

  it('bounds Monte Carlo odds in copied posts and the exported image', async () => {
    const canvas = captureCanvas();
    const payload = structuredClone(mockPayload);
    payload.analysis.method = 'Monte Carlo (20,000 scenarios)';
    payload.analysis.overallProbabilities.Gujarat.top4 = 0.04;

    const posts = shareTexts(payload);
    await exportRacePng(payload);

    for (const post of Object.values(posts)) {
      expect(post).toContain('RR (>99.9%)');
      expect(post).toContain('GT (<0.1%)');
    }
    expect(canvas.texts.map(({ value }) => value)).toContain('>99.9%');
    expect(canvas.texts.map(({ value }) => value)).toContain('<0.1%');
    expect(raceCaption(payload)).toContain('Monte Carlo');
    expect(raceCaption(payload)).not.toContain('Exact all-combinations');
  });

  it('retains exact certainty when the model enumerates every scenario', () => {
    expect(shareTexts(mockPayload).whatsapp).toContain('RR (100%)');
    expect(raceCaption(mockPayload)).toContain('Exact all-combinations');
  });

  it('waits for the self-hosted fonts before painting the export', async () => {
    const canvas = captureCanvas();
    let finishFonts!: () => void;
    Object.defineProperty(document.fonts, 'ready', { value: new Promise<void>((resolve) => { finishFonts = resolve; }) });

    const exporting = exportRacePng(mockPayload);
    await Promise.resolve();
    expect(canvas.texts).toHaveLength(0);
    finishFonts();
    await exporting;

    expect(canvas.texts.some(({ font }) => font.includes('Barlow Semi Condensed'))).toBe(true);
    expect(canvas.texts.some(({ font }) => font.includes('IBM Plex Sans Variable'))).toBe(true);
  });
});
