/// <reference types="vitest/globals" />
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { finalPayload, installFetch } from './test/fixtures';

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    installFetch();
  });

  it('loads the canonical payload and renders the playoff pulse surface', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'IPL Top 4 Qualification Probabilities' })).toBeInTheDocument();
    expect(screen.getByText('Updated daily after the night match')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: "Today's Race Summary" })).toBeInTheDocument();
    expect(screen.getByTestId('freshness-warning')).toHaveTextContent('Test source warning');
    expect(screen.getByText('Royal Challengers Bengaluru')).toBeInTheDocument();
    expect(screen.getAllByText('CSK').length).toBeGreaterThan(0);
    expect(screen.getAllByText('MI').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Top 4 Odds' })).toBeInTheDocument();
    expect(screen.getByText(/Equal points do not imply equal odds/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^caption$/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId('reels-gallery')).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Share kit' })[0]).toHaveAttribute('href', '/share.html');
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/ipl-2026.json', { cache: 'no-cache' });
  });

  it('sorts the standings by points, then NRR, then wins', async () => {
    const { container } = render(<App />);
    await screen.findByTestId('standings-ladder');

    const rows = Array.from(container.querySelectorAll('.standing-row')).map((row) => row.textContent || '');

    expect(rows[0]).toContain('PBKS');
    expect(rows[1]).toContain('RCB');
    expect(rows[2]).toContain('SRH');
  });

  it('selects a team from a deep link hash', async () => {
    window.history.replaceState(null, '', '/#team=CSK');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Chennai Super Kings' })).toBeInTheDocument();
    expect(screen.getByText(/CSK need wins and rival results immediately/)).toBeInTheDocument();
  });

  it('renders metadata and update dates in small trust surfaces', async () => {
    render(<App />);

    expect(await screen.findByTestId('latest-update')).toHaveTextContent('2026');
    expect(screen.getAllByText(/Source: CricketData/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Probabilities exclude NRR simulation/)).toBeInTheDocument();
  });
});

describe('App after the season ends', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    installFetch(finalPayload);
  });

  it('shows the champion, final table and playoff results instead of live odds', async () => {
    const { container } = render(<App />);

    expect(await screen.findByRole('heading', { name: 'IPL 2026 Final Standings' })).toBeInTheDocument();
    expect(screen.getByText('Season complete · Royal Challengers Bengaluru are champions')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Season Summary' })).toBeInTheDocument();
    expect(screen.getByText('SRH also reached 18 pts but had a lower NRR.')).toBeInTheDocument();
    expect(screen.getByText('5th on 15 pts, 1 pt behind RR.')).toBeInTheDocument();

    const playoffs = screen.getByTestId('playoffs-panel');
    expect(playoffs).toHaveTextContent('Qualifier 1');
    expect(playoffs).toHaveTextContent('RCB won by 92 runs');
    expect(playoffs).toHaveTextContent('Royal Challengers Bengaluru won the IPL 2026 title.');

    const rows = Array.from(container.querySelectorAll('.standing-row')).map((row) => row.textContent || '');
    expect(rows[0]).toMatch(/^1RCB/);
    expect(rows[1]).toMatch(/^2GT/);
    expect(rows[2]).toMatch(/^3SRH/);
    expect(rows[0]).toContain('+0.783');

    expect(screen.queryByRole('heading', { name: 'Top 4 Odds' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('reels-gallery')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Licence: ODC-By 1.0/ })).toHaveAttribute(
      'href',
      'https://opendatacommons.org/licenses/by/1-0/',
    );
    expect(document.title).toBe('IPL 2026 Final Standings, NRR & Playoff Results | IPL Playoff Pulse');
  });

  it('shows a team season outcome from a deep link', async () => {
    window.history.replaceState(null, '', '/#team=RR');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Rajasthan Royals' })).toBeInTheDocument();
    expect(screen.getByText('Knocked out in Qualifier 2')).toBeInTheDocument();
    expect(screen.getByText('Eliminator: RR vs SRH')).toBeInTheDocument();
  });
});
