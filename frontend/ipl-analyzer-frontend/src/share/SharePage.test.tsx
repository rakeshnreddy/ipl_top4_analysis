/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { finalPayload, installFetch } from '../test/fixtures';
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
    expect(screen.getByText('2026-05-04')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /download/i })).toHaveLength(2);
    expect(screen.getByRole('button', { name: /instagram caption/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /x short post/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /whatsapp share text/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /race png/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to standings/i })).toHaveAttribute('href', '/');
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

  it('hides race post tools once the league stage is over', async () => {
    installFetch(finalPayload);

    render(<SharePage />);

    expect(await screen.findByText(/league stage is over/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /whatsapp share text/i })).not.toBeInTheDocument();
    expect(await screen.findByTestId('reels-gallery')).toBeInTheDocument();
  });
});
