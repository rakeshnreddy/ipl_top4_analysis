/// <reference types="vitest/globals" />
import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Root from './Root';
import { finalPayload, installFetch, leagueIndex, mockManifest, wplFinalPayload, wplLivePayload } from './test/fixtures';

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    installFetch();
  });

  it('loads the canonical payload and renders the playoff pulse surface', async () => {
    render(<Root />);

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
    const { container } = render(<Root />);
    await screen.findByTestId('standings-ladder');

    const rows = Array.from(container.querySelectorAll('.standing-row')).map((row) => row.textContent || '');

    expect(rows[0]).toContain('PBKS');
    expect(rows[1]).toContain('RCB');
    expect(rows[2]).toContain('SRH');
  });

  it('selects a team from a deep link hash', async () => {
    window.history.replaceState(null, '', '/#team=CSK');

    render(<Root />);

    expect(await screen.findByRole('heading', { name: 'Chennai Super Kings' })).toBeInTheDocument();
    expect(screen.getByText(/CSK need wins and rival results immediately/)).toBeInTheDocument();
  });

  it('renders metadata and update dates in small trust surfaces', async () => {
    render(<Root />);

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
    const { container } = render(<Root />);

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
    await waitFor(() => expect(document.title).toBe('IPL 2026 Final Standings, NRR & Playoff Results | IPL Playoff Pulse'));
  });

  it('shows a team season outcome from a deep link', async () => {
    window.history.replaceState(null, '', '/#team=RR');

    render(<Root />);

    expect(await screen.findByRole('heading', { name: 'Rajasthan Royals' })).toBeInTheDocument();
    expect(screen.getByText('Knocked out in Qualifier 2')).toBeInTheDocument();
    expect(screen.getByText('Eliminator: RR vs SRH')).toBeInTheDocument();
  });
});

describe('App with several leagues', () => {
  const routes = { '/data/leagues.json': leagueIndex, '/data/wpl-2026.json': wplFinalPayload };

  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    installFetch(finalPayload, mockManifest, routes);
  });

  it('loads the league named in ?league= and uses its playoff format', async () => {
    window.history.replaceState(null, '', '/?league=wpl-2026');

    const { container } = render(<Root />);

    expect(await screen.findByRole('heading', { name: 'WPL 2026 Final Standings' })).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/wpl-2026.json', { cache: 'no-cache' });
    expect(screen.getByText('Top 3 after 20 league matches.')).toBeInTheDocument();
    expect(screen.getByText('Top 1 finish')).toBeInTheDocument();
    expect(screen.getByText('4th on 6 pts, 2 pts behind DC.')).toBeInTheDocument();
    expect(screen.getByTestId('playoffs-panel')).toHaveTextContent('Royal Challengers Bengaluru won the WPL 2026 title.');

    const stripe = container.querySelector<HTMLElement>('.standing-row .team-stripe');
    expect(stripe?.style.backgroundColor).toBe('rgb(236, 28, 36)');
    await waitFor(() => expect(document.title).toBe('WPL 2026 Final Standings, NRR & Playoff Results | WPL Playoff Pulse'));
    await waitFor(() =>
      expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute(
        'href',
        'http://localhost:3000/?league=wpl-2026',
      ),
    );
  });

  it('switches leagues with plain links that mark the current one', async () => {
    window.history.replaceState(null, '', '/?league=wpl-2026');

    render(<Root />);

    const switcher = await screen.findByRole('navigation', { name: 'Leagues' });
    expect(switcher.querySelector('a[aria-current="page"]')).toHaveTextContent('WPL 2026');
    expect(screen.getByRole('link', { name: 'IPL 2026' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'WPL 2026' })).toHaveAttribute('href', '/?league=wpl-2026');
  });

  it('treats an Eliminator loss as an exit when the league gives no second chance', async () => {
    window.history.replaceState(null, '', '/?league=wpl-2026#team=GG');

    render(<Root />);

    expect(await screen.findByRole('heading', { name: 'Gujarat Giants' })).toBeInTheDocument();
    expect(screen.getByText('Knocked out in Eliminator')).toBeInTheDocument();
  });

  it('offers a way back when the requested league does not exist', async () => {
    window.history.replaceState(null, '', '/?league=nope-2026');

    render(<Root />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load nope-2026 data (404).');
    expect(screen.getByRole('link', { name: 'Go to the IPL page' })).toHaveAttribute('href', '/');
  });
});

describe('App during another league\'s season', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('shows live odds in the league\'s own qualification format', async () => {
    installFetch(finalPayload, mockManifest, { '/data/wpl-2027.json': wplLivePayload(true) });
    window.history.replaceState(null, '', '/?league=wpl-2027');

    const { container } = render(<Root />);

    expect(await screen.findByRole('heading', { name: 'WPL Top 3 Qualification Probabilities' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Top 3 Odds' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Top 3' })).toHaveClass('active');
    expect(screen.getByRole('button', { name: 'Top 1' })).toBeInTheDocument();
    expect(screen.getByText('GG +12.5')).toBeInTheDocument();
    expect(screen.getByText('UPW -8.0')).toBeInTheDocument();
    expect(container.querySelector('.standing-row .top4-prob')).toHaveTextContent('98.5%');
    expect(screen.queryByRole('link', { name: 'Share kit' })).not.toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe('WPL Top 3 Qualification Chances Today | WPL Playoff Pulse'));
  });

  it('shows the opening match instead of a race before the first result', async () => {
    installFetch(finalPayload, mockManifest, { '/data/wpl-2027.json': wplLivePayload(false) });
    window.history.replaceState(null, '', '/?league=wpl-2027');

    render(<Root />);

    const heroFacts = await screen.findByLabelText('Race snapshot');
    expect(within(heroFacts).getByText('Opening match')).toBeInTheDocument();
    expect(within(heroFacts).getByText('RCB vs GG')).toBeInTheDocument();
    expect(within(heroFacts).getByText('3 of 5 teams')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: "Today's Race Summary" })).not.toBeInTheDocument();
    expect(screen.getByText('Every team starts level; the odds move as results come in.')).toBeInTheDocument();
  });
});

describe('App home page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    window.history.replaceState(null, '', '/');
  });

  it('shows the league the index names as default', async () => {
    installFetch(finalPayload, mockManifest, {
      '/data/leagues.json': { ...leagueIndex, default: 'wpl-2026' },
      '/data/wpl-2026.json': wplFinalPayload,
    });

    render(<Root />);

    expect(await screen.findByRole('heading', { name: 'WPL 2026 Final Standings' })).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/wpl-2026.json', { cache: 'no-cache' });
    expect(globalThis.fetch).not.toHaveBeenCalledWith('/data/ipl-2026.json', { cache: 'no-cache' });
  });

  it('shows ties and bonus points when a league has them', async () => {
    const standings = finalPayload.standings.map((team) =>
      team.teamKey === 'Punjab' ? { ...team, wins: 6, noResult: 0, ties: 1, bonusPoints: 2 } : team,
    );
    installFetch({ ...finalPayload, standings });
    window.history.replaceState(null, '', '/#team=PBKS');

    const { container } = render(<Root />);

    await screen.findByRole('heading', { name: 'Punjab Kings' });
    expect(container.querySelector('.deep-dive-grid')).toHaveTextContent('6W-6L-1T-0NR');
    expect(screen.getByText('League stage · 2 bonus points')).toBeInTheDocument();
  });
});

