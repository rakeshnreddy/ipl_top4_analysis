export interface ReelsSlide {
  date: string | null;
  fileName: string;
  path: string;
  downloadName: string;
  imageWidth: number;
  imageHeight: number;
}

export interface ReelsManifest {
  latestDate: string | null;
  dates: string[];
  slides: ReelsSlide[];
  generatedAt: string;
  source: {
    name?: string | null;
    url?: string | null;
    dataGeneratedAt?: string | null;
  };
  warnings: string[];
  imageWidth: number;
  imageHeight: number;
  latestPackPath?: string | null;
  latestPreviewPath?: string | null;
}

export const reelsManifestUrl = `${import.meta.env.BASE_URL}social/instagram-carousel/manifest.json`;

const isString = (value: unknown): value is string => typeof value === 'string';

function assertManifest(payload: unknown): asserts payload is ReelsManifest {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Reels manifest is empty or malformed.');
  }

  const candidate = payload as Partial<ReelsManifest>;
  if (!Array.isArray(candidate.dates) || !Array.isArray(candidate.slides)) {
    throw new Error('Reels manifest is missing dates or slides.');
  }

  if (!isString(candidate.generatedAt) || typeof candidate.imageWidth !== 'number' || typeof candidate.imageHeight !== 'number') {
    throw new Error('Reels manifest is missing generatedAt or image dimensions.');
  }

  candidate.slides.forEach((slide) => {
    if (!isString(slide.path) || !isString(slide.fileName) || !isString(slide.downloadName)) {
      throw new Error('One or more Reels slides are missing file metadata.');
    }
  });
}

export function publicAssetUrl(path: string | null | undefined): string {
  return path ? `${import.meta.env.BASE_URL}${path}` : '';
}

export async function loadReelsManifest(fetchImpl: typeof fetch = fetch): Promise<ReelsManifest> {
  const response = await fetchImpl(reelsManifestUrl, { cache: 'no-cache' });
  if (!response.ok) {
    throw new Error(`Unable to load Reels manifest (${response.status}).`);
  }

  const payload = await response.json();
  assertManifest(payload);
  return payload;
}
