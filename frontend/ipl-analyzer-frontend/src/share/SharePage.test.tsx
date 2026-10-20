/// <reference types="vitest/globals" />
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import SharePage from './SharePage';

describe('SharePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    installFetch();
  });

  it('renders the Reels gallery from the latest manifest', async () => {
    render(<SharePage />);

    const gallery = await screen.findByTestId('reels-gallery');

    expect(gallery.querySelectorAll('img')).toHaveLength(2);
    expect(gallery.querySelector('img')).toHaveAttribute('src', `/${mockManifest.slides[0].path}`);
    expect(screen.getByText('2026-05-04')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /download/i })).toHaveLength(2);
    expect(screen.getByRole('button', { name: /instagram caption/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /x short post/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /whatsapp share text/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /race png/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to standings/i })).toHaveAttribute('href', '/league/ipl-2026/');
  });

  it('copies Reels share text from caption buttons', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    render(<SharePage />);

    fireEvent.click(await screen.findByRole('button', { name: /whatsapp share text/i }));

    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(writeText.mock.calls[0][0]).toContain('IPL Playoff Pulse');
    expect(writeText.mock.calls[0][0]).toContain('Top 4: PBKS, RCB, SRH, RR');
  });

  it('prioritises the first visible slide and defers the remaining gallery images', async () => {
    render(<SharePage />);
    const images = (await screen.findByTestId('reels-gallery')).querySelectorAll('img');

    expect(images[0]).toHaveAttribute('loading', 'eager');
    expect(images[0]).toHaveAttribute('fetchpriority', 'high');
    expect(images[1]).toHaveAttribute('loading', 'lazy');
    expect(images[1]).not.toHaveAttribute('fetchpriority');
  });

  it('uses the gallery preview while keeping full-size PNG links and downloads', async () => {
    const slide = mockManifest.slides[0];
    installFetch(undefined, {
      ...mockManifest,
      slides: [{ ...slide, previewPath: 'social/instagram-carousel/2026-05-04/slide-01-overview.preview.webp', previewWidth: 720, previewHeight: 1280 }],
    });
    render(<SharePage />);

    const image = await screen.findByAltText('IPL Playoff Pulse Reels slide 1');
    expect(image).toHaveAttribute('src', '/social/instagram-carousel/2026-05-04/slide-01-overview.preview.webp');
    expect(image).toHaveAttribute('width', '720');
    expect(image).toHaveAttribute('height', '1280');
    expect(image.closest('a')).toHaveAttribute('href', `/${slide.path}`);
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute('href', `/${slide.path}`);
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute('download', slide.downloadName);
  });

  it('keeps later slides off the network until they approach the viewport', async () => {
    let intersect!: IntersectionObserverCallback;
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback) { intersect = callback; }
      observe() {}
      disconnect() {}
    });
    try {
      render(<SharePage />);
      const images = (await screen.findByTestId('reels-gallery')).querySelectorAll('img');
      expect(images[0]).toHaveAttribute('src', `/${mockManifest.slides[0].path}`);
      expect(images[1]).not.toHaveAttribute('src');

      act(() => intersect([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver));
      expect(images[1]).toHaveAttribute('src', `/${mockManifest.slides[1].path}`);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('falls back to the original PNG when an optional preview cannot load', async () => {
    const slide = mockManifest.slides[0];
    installFetch(undefined, { ...mockManifest, slides: [{ ...slide, previewPath: 'social/missing.webp', previewWidth: 720, previewHeight: 1280 }] });
    render(<SharePage />);
    const image = await screen.findByAltText('IPL Playoff Pulse Reels slide 1');

    fireEvent.error(image);

    expect(image).toHaveAttribute('src', `/${slide.path}`);
    expect(image).toHaveAttribute('width', '1080');
    fireEvent.error(image);
    expect(image).toHaveAttribute('src', `/${slide.path}`);
  });

  it('labels each archived graphic with its own date in a mixed-date pack', async () => {
    installFetch(undefined, { ...mockManifest, slides: [{ ...mockManifest.slides[0], date: '2025-05-04' }, mockManifest.slides[1]] });
    render(<SharePage />);

    expect(await screen.findByText('Archive · 2025-05-04')).toBeInTheDocument();
    expect(screen.getByText('Archive · 2026-05-04')).toBeInTheDocument();
  });

  it('hides race post tools once the league stage is over', async () => {
    installFetch(finalPayload);

    render(<SharePage />);

    expect(await screen.findByText(/league stage is over/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /whatsapp share text/i })).not.toBeInTheDocument();
    expect(await screen.findByTestId('reels-gallery')).toBeInTheDocument();
    expect(screen.getByText('Archived pack')).toBeInTheDocument();
    expect(screen.getAllByText(/Archive · 2026-05-04/)).toHaveLength(2);
  });

  it('reports a failed clipboard operation without claiming success', async () => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn().mockRejectedValue(new Error('Unavailable')) } });
    Object.defineProperty(document, 'execCommand', { configurable: true, value: vi.fn().mockReturnValue(false) });
    render(<SharePage />);
    fireEvent.click(await screen.findByRole('button', { name: /race caption/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be copied');
    expect(screen.queryByText('Copied. Your post text is ready.')).not.toBeInTheDocument();
    expect(document.querySelector('textarea')).not.toBeInTheDocument();
  });

  it('marks an older pack as archived while the current season is still active', async () => {
    installFetch(undefined, { ...mockManifest, source: { ...mockManifest.source, dataGeneratedAt: '2025-05-04T08:00:00Z' } });
    render(<SharePage />);
    expect(await screen.findByText('Archived pack')).toBeInTheDocument();
    expect(screen.getByText(/earlier data update/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /race caption/i })).toBeInTheDocument();
  });
});
