/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Root from '../Root';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import { conferencePayload, footballPayload, multiSportIndex } from '../test/sportFixtures';
import { formatChance } from './format';

function openLeague(path: string, payload = footballPayload) {
  window.history.replaceState(null, '', path);
  installFetch(finalPayload, mockManifest, {
    '/data/leagues.json': multiSportIndex,
    '/data/epl-2026-27.json': payload,
  });
  return render(<Root />);
}

describe('SportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('routes a football league to the table and season odds', async () => {
    openLeague('/?league=epl-2026-27');

    expect(await screen.findByRole('heading', { name: 'Premier League Title, Top 2 & Relegation Odds' })).toBeInTheDocument();
    const table = screen.getByRole('table');
    const rows = within(table).getAllByRole('row');
    expect(rows[1]).toHaveTextContent('ARS');
    expect(rows[1]).toHaveTextContent('81%');
    expect(rows[1]).toHaveTextContent('>99.9%');
    expect(rows[4]).toHaveTextContent('87%');
    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent('ARS 81%');
    await waitFor(() => expect(document.title).toBe('Premier League 2026-27 Odds: Title, Top 2 & Relegation Chances | Playoff Pulse'));
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/epl-2026-27.json', { cache: 'no-cache' });
  });

  it('shows fixture predictions, swing games and the biggest moves', async () => {
    openLeague('/?league=epl-2026-27');

    const fixtures = await screen.findByRole('heading', { name: 'Fixture Predictions' });
    const fixturePanel = fixtures.closest('section')!;
    expect(within(fixturePanel).getByLabelText('Home 20%, Draw 25%, Away 55%')).toBeInTheDocument();

    const matters = screen.getByRole('heading', { name: 'Matches That Matter' }).closest('section')!;
    expect(within(matters).getByText("ARS's title chance after each result")).toBeInTheDocument();
    expect(within(matters).getByText('88%')).toBeInTheDocument();

    const moves = screen.getByRole('heading', { name: 'Biggest Moves' }).closest('section')!;
    expect(within(moves).getByText('ARS +6.5')).toBeInTheDocument();
  });

  it('opens a team from a deep link with its finishing-position chances', async () => {
    openLeague('/?league=epl-2026-27#team=TOT');

    const panel = (await screen.findByRole('heading', { name: 'Tottenham Hotspur' })).closest('aside')!;
    expect(within(panel).getByRole('figure', { name: 'Finishing position chances for TOT' })).toBeInTheDocument();
    // Spurs host Arsenal: the win/draw/loss split is from Spurs' side.
    expect(within(panel).getByText('Win 20% · Draw 25% · Loss 55%')).toBeInTheDocument();
  });

  it('marks finished races instead of showing odds once the season is over', async () => {
    openLeague('/?league=epl-2026-27', {
      ...footballPayload,
      metadata: { ...footballPayload.metadata, season_status: 'complete' },
      fixtures: [],
      matchesThatMatter: [],
      analysis: {
        ...footballPayload.analysis,
        probabilities: {
          Arsenal: { title: 100, top2: 100, relegation: 0 },
          Liverpool: { title: 0, top2: 100, relegation: 0 },
          Chelsea: { title: 0, top2: 0, relegation: 0 },
          Spurs: { title: 0, top2: 0, relegation: 100 },
        },
      },
    });

    expect(await screen.findByRole('heading', { name: 'Premier League 2026-27 Final Table' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Fixture Predictions' })).not.toBeInTheDocument();
    expect(within(screen.getAllByRole('row')[1]).getAllByText('✓')).toHaveLength(2);
  });

  it('groups the league switcher by sport', async () => {
    openLeague('/?league=epl-2026-27');

    fireEvent.click(await screen.findByRole('button', { name: 'Leagues: Premier League 2026-27' }));
    const nav = screen.getByRole('navigation', { name: 'Leagues' });
    expect(within(nav).getByText('Football')).toBeInTheDocument();
    expect(within(nav).getByText('Cricket')).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: /Premier League 2026-27/ })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: /IPL 2026/ })).toHaveAttribute('href', '/');
  });
});

describe('SportPage for leagues with conferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('shows a conference in seed order with its playoff line', async () => {
    openLeague('/?league=epl-2026-27', conferencePayload);

    expect(await screen.findByRole('heading', { name: 'NFL Playoff & Super Bowl Odds' })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe('NFL Playoff & Super Bowl Odds 2026 | Playoff Pulse'));
    fireEvent.click(screen.getByRole('button', { name: 'AFC' }));

    // The cut line is decorative (aria-hidden), so read the rows from the DOM.
    const rows = Array.from(screen.getByRole('table').querySelectorAll('tbody tr')).map((row) => row.textContent);
    expect(rows[0]).toContain('CHE');
    expect(rows[1]).toBe('Playoff line');
    expect(rows[2]).toContain('ARS');
    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent('Super Bowl favourite');
  });

  it('describes a team by its record and conference seed', async () => {
    openLeague('/?league=epl-2026-27#team=LIV', conferencePayload);

    const panel = (await screen.findByRole('heading', { name: 'Liverpool' })).closest('aside')!;
    expect(within(panel).getByText(/2-1 · 1/)).toHaveTextContent('2-1 · 1st NFC');
    expect(within(panel).getByText(/10 wins/)).toHaveTextContent('avg seed 1.3');
    expect(within(panel).getByRole('figure', { name: 'Conference seed chances for LIV' })).toBeInTheDocument();
  });
});

describe('SportPage during the playoffs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('ticks settled places, keeps title odds live and shows the bracket', async () => {
    openLeague('/?league=epl-2026-27', {
      ...conferencePayload,
      metadata: { ...conferencePayload.metadata, season_status: 'postseason' },
      league: {
        ...conferencePayload.league,
        tiers: [
          { key: 'playoffs', label: 'Playoffs', kind: 'playoffs', settled: true },
          { key: 'title', label: 'Super Bowl', kind: 'champion' },
        ],
      },
      analysis: {
        ...conferencePayload.analysis,
        probabilities: {
          Arsenal: { playoffs: 0, title: 0 },
          Chelsea: { playoffs: 100, title: 41.5 },
          Liverpool: { playoffs: 100, title: 58.5 },
          Spurs: { playoffs: 0, title: 0 },
        },
      },
      bracket: {
        champion: null,
        rounds: [
          {
            key: 'CONF',
            label: 'Conference Championship',
            series: [
              { stage: 'CONF', conference: 'AFC', top: 'Chelsea', bottom: 'Arsenal', topSeed: 1, bottomSeed: 2, topWins: 1, bottomWins: 0, bestOf: 1, winner: 'Chelsea' },
            ],
          },
          {
            key: 'SB',
            label: 'Super Bowl',
            series: [{ stage: 'SB', conference: null, top: null, bottom: null, topSeed: null, bottomSeed: null, topWins: 0, bottomWins: 0, bestOf: 1, winner: null }],
          },
        ],
      },
    });

    const bracket = (await screen.findByRole('heading', { name: 'Playoff Bracket' })).closest('section')!;
    expect(within(bracket).getByText('1–0')).toBeInTheDocument();
    expect(within(bracket).getByText('1 CHE')).toHaveClass('is-winner');
    expect(within(bracket).getAllByText('To be decided')).toHaveLength(2);

    const chelsea = within(screen.getByRole('table')).getAllByRole('row').find((row) => row.textContent?.includes('CHE'))!;
    expect(within(chelsea).getByText('✓')).toBeInTheDocument();
    expect(within(chelsea).getByText('42%')).toBeInTheDocument();
    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent('Super Bowl favourite');
  });
});

describe('formatChance', () => {
  it('never rounds a Monte Carlo estimate to a certainty', () => {
    expect(formatChance(99.96)).toBe('>99.9%');
    expect(formatChance(99.6)).toBe('99.6%');
    expect(formatChance(42.4)).toBe('42%');
    expect(formatChance(0.4)).toBe('0.4%');
    expect(formatChance(0.04)).toBe('<0.1%');
    expect(formatChance(0)).toBe('–');
  });
});
