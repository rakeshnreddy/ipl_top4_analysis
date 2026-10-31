/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Root from '../Root';
import { f1Index, f1Payload } from '../test/f1Fixtures';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import type { F1Payload } from './f1Data';

function openF1(path = '/?league=f1-2026', payload: F1Payload = f1Payload) {
  window.history.replaceState(null, '', path);
  installFetch(finalPayload, mockManifest, {
    '/data/leagues.json': f1Index,
    '/data/f1-2026.json': payload,
  });
  return render(<Root />);
}

const tableRows = (name: RegExp) => within(screen.getByRole('table', { name })).getAllByRole('row');

describe('F1Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('opens exact-position odds for both full championship fields', async () => {
    openF1();

    expect(await screen.findByRole('heading', { name: 'F1 2026 Championship Odds' })).toBeInTheDocument();
    expect(screen.getByTestId('f1-page')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'All positions', pressed: true })).toBeInTheDocument();

    const drivers = tableRows(/Drivers' exact championship position odds/);
    expect(drivers).toHaveLength(5);
    expect(drivers[1]).toHaveTextContent('VER');
    expect(drivers[1]).toHaveTextContent('Red Bull Racing');
    expect(drivers[1]).toHaveTextContent('300');
    expect(within(drivers[1]).getByLabelText('VER P1: 54%')).toBeInTheDocument();
    expect(within(drivers[1]).getByLabelText('VER P4: 1%')).toBeInTheDocument();
    expect(drivers[4]).toHaveTextContent('TSU');
    expect(within(drivers[4]).getByLabelText('TSU P4: 95%')).toBeInTheDocument();
    expect(within(drivers[0]).getByRole('columnheader', { name: 'P4' })).toHaveAttribute('scope', 'col');
    expect(within(drivers[1]).getByRole('rowheader')).toHaveAttribute('scope', 'row');

    const teams = tableRows(/Constructors' exact championship position odds/);
    expect(teams).toHaveLength(4);
    expect(teams[1]).toHaveTextContent('Mercedes');
    expect(teams[1]).toHaveTextContent('ANT · RUS');
    expect(teams[1]).toHaveTextContent('480');
    expect(within(teams[1]).getByLabelText('MER P2: 20%')).toBeInTheDocument();
    expect(within(teams[3]).getByLabelText('RB P3: >99.9%')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Drivers position odds, scroll for all positions' })).toHaveAttribute('tabindex', '0');
    expect(screen.getByRole('region', { name: 'Constructors position odds, scroll for all positions' })).toHaveAttribute('tabindex', '0');
    expect(screen.getAllByText(/Each column is one exact finishing position, not a cumulative top/)).toHaveLength(2);

    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent("Drivers' title favouriteVER 54%");
    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent("Constructors' title favouriteMER 80%");
    await waitFor(() => expect(document.title).toBe("F1 2026 Championship Odds: All Finishing Positions | Playoff Pulse"));
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/f1-2026.json', { cache: 'no-cache' });
  });

  it('keeps the original points, wins and cumulative title/top-three tables in Standings', async () => {
    openF1();
    fireEvent.click(await screen.findByRole('button', { name: 'Standings' }));
    expect(screen.getByRole('button', { name: 'Standings', pressed: true })).toBeInTheDocument();
    const drivers = tableRows(/Drivers' standings/);
    expect(drivers[1]).toHaveTextContent('54%');
    expect(drivers[1]).toHaveTextContent('99%');
    expect(within(drivers[0]).getByRole('columnheader', { name: 'Wins' })).toBeInTheDocument();
    expect(tableRows(/Constructors' standings/)[1]).toHaveTextContent('80%');
    fireEvent.click(screen.getByRole('button', { name: 'All positions' }));
    expect(screen.getByRole('table', { name: /Drivers' exact championship position odds/ })).toBeInTheDocument();
    expect(window.location.search).toBe('?league=f1-2026');
  });

  it('uses the entire dynamic field, including replaced drivers and every constructor position', async () => {
    const standings = Array.from({ length: 23 }, (_, index) => ({
      ...f1Payload.standings[index % 4], teamKey: `driver_${index}`, shortName: `D${index + 1}`,
      fullName: `Driver ${index + 1}`, rank: index + 1, racing: index < 22,
    }));
    const constructorStandings = Array.from({ length: 11 }, (_, index) => ({
      ...f1Payload.constructorStandings[index % 3], teamKey: `team_${index}`, shortName: `T${index + 1}`,
      fullName: `Team ${index + 1}`, rank: index + 1,
    }));
    const positions = Object.fromEntries(standings.map((row, index) => [row.teamKey, standings.map((_, position) => position === index ? 100 : 0)]));
    const constructorPositions = Object.fromEntries(constructorStandings.map((row, index) => [row.teamKey, constructorStandings.map((_, position) => position === index ? 100 : 0)]));
    openF1('/?league=f1-2026', { ...f1Payload, standings, constructorStandings, analysis: { ...f1Payload.analysis, positions, constructorPositions } });

    const drivers = await screen.findByRole('table', { name: /Drivers' exact championship position odds/ });
    expect(within(drivers).getAllByRole('row')).toHaveLength(24);
    expect(within(drivers).getByRole('columnheader', { name: 'P23' })).toBeInTheDocument();
    expect(within(drivers).getByLabelText('D23 P23: >99.9%')).toBeInTheDocument();
    const teams = screen.getByRole('table', { name: /Constructors' exact championship position odds/ });
    expect(within(teams).getAllByRole('row')).toHaveLength(12);
    expect(within(teams).getByRole('columnheader', { name: 'P11' })).toBeInTheDocument();
    expect(within(teams).getByLabelText('T11 P11: >99.9%')).toBeInTheDocument();
  });

  it('distinguishes zero simulated finishes from missing or malformed position rows', async () => {
    openF1('/?league=f1-2026', {
      ...f1Payload,
      analysis: { ...f1Payload.analysis, positions: {
        max_verstappen: [54, 31, 14, 1], antonelli: [44.5, 35.5],
        russell: [1.5, 33.5, Number.NaN, 2], tsunoda: [0, 0, 5, 95],
      }, constructorPositions: undefined },
    });
    const drivers = within(await screen.findByRole('table', { name: /Drivers' exact championship position odds/ }));
    expect(drivers.getByLabelText('TSU P1: 0%')).toHaveTextContent('–');
    const rows = drivers.getAllByRole('row');
    expect(within(rows[2]).getByText('Unavailable')).toHaveAttribute('colspan', '4');
    expect(within(rows[3]).getByText('Unavailable')).toBeInTheDocument();
    const teams = within(screen.getByRole('table', { name: /Constructors' exact championship position odds/ }));
    expect(teams.getAllByText('Unavailable')).toHaveLength(3);
    expect(screen.getAllByText(/– means no simulated finishes/)).toHaveLength(2);
  });

  it.each([[101, 0, 0, -1], [null, 0, 0, 100], { title: 54 }].map((row) => ({ row })))('does not turn invalid position data into an invented distribution: $row', async ({ row }) => {
    const payload = { ...f1Payload, analysis: { ...f1Payload.analysis, positions: { max_verstappen: row } } } as unknown as F1Payload;
    openF1('/?league=f1-2026', payload);
    const table = await screen.findByRole('table', { name: /Drivers' exact championship position odds/ });
    expect(within(within(table).getAllByRole('row')[1]).getByText('Unavailable')).toBeInTheDocument();
  });

  it('keeps legacy payloads readable without inferring exact positions from title/top-three odds', async () => {
    openF1('/?league=f1-2026', { ...f1Payload, analysis: { ...f1Payload.analysis, positions: undefined, constructorPositions: undefined } });
    const table = await screen.findByRole('table', { name: /Drivers' exact championship position odds/ });
    expect(within(table).getAllByText('Unavailable')).toHaveLength(4);
    fireEvent.click(screen.getByRole('button', { name: 'Standings' }));
    expect(tableRows(/Drivers' standings/)[1]).toHaveTextContent('54%');
  });

  it('never rounds simulated certainty to a final result', async () => {
    openF1('/?league=f1-2026', { ...f1Payload, analysis: { ...f1Payload.analysis, positions: {
      max_verstappen: [99.99, 0.01, 0, 0], antonelli: [0.01, 99.99, 0, 0],
      russell: [0, 0, 100, 0], tsunoda: [0, 0, 0, 100],
    } } });
    const table = await screen.findByRole('table', { name: /Drivers' exact championship position odds/ });
    expect(within(table).getByLabelText('VER P1: >99.9%')).toHaveTextContent('>99.9%');
    expect(within(table).queryByText('100%')).not.toBeInTheDocument();
  });

  it('lists the next races with their favourites and the latest podium', async () => {
    openF1();

    const races = (await screen.findByRole('heading', { name: 'Next Races' })).closest('section')!;
    expect(within(races).getByRole('heading', { name: 'Singapore Grand Prix · Sprint' })).toBeInTheDocument();
    const sprint = within(races).getByRole('table', { name: 'Favourites for the Singapore Grand Prix · Sprint' });
    expect(within(sprint).getAllByRole('row')[1]).toHaveTextContent('VER42%80%');

    const results = screen.getByRole('heading', { name: 'Recent Results' }).closest('section')!;
    expect(within(results).getByText('Bahrain Grand Prix in Malaysia')).toBeInTheDocument();
    expect(within(results).getByLabelText('Podium: VER, ANT, RUS')).toBeInTheDocument();

    const method = screen.getByRole('heading', { name: 'How These Odds Work' }).closest('section')!;
    expect(within(method).getByText(/Plackett-Luce/)).toBeInTheDocument();
    expect(within(method).getByRole('link', { name: 'FIA 2026 Formula 1 Regulations, Section A' })).toHaveAttribute('href', 'https://www.fia.com/');
  });

  it.each(['/', '/ipl_top4_analysis/'])('keeps the league in section links and the skip link under %s', async (base) => {
    openF1(`${base}?league=f1-2026`);

    const sections = await screen.findByRole('navigation', { name: 'Page sections' });
    // The page has <base href="/">: a bare "#constructors" would open the home page instead.
    expect(within(sections).getByRole('link', { name: 'Drivers' })).toHaveAttribute('href', `${base}?league=f1-2026#drivers`);
    expect(within(sections).getByRole('link', { name: 'Constructors' })).toHaveAttribute('href', `${base}?league=f1-2026#constructors`);
    expect(within(sections).getByRole('link', { name: 'Next races' })).toHaveAttribute('href', `${base}?league=f1-2026#races`);
    expect(within(sections).getByRole('link', { name: 'How it works' })).toHaveAttribute('href', `${base}?league=f1-2026#method`);
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', `${base}?league=f1-2026#main`);

    fireEvent.click(within(sections).getByRole('link', { name: 'Constructors' }));
    await waitFor(() => expect(window.location.hash).toBe('#constructors'));
    expect(window.location.search).toBe('?league=f1-2026');
  });

  it('lists F1 under Motorsport in the league menu', async () => {
    openF1();

    fireEvent.click(await screen.findByRole('button', { name: /F1 2026/ }));
    const menu = screen.getByRole('navigation', { name: 'Leagues' });
    expect(within(menu).getByText('Motorsport')).toBeInTheDocument();
    expect(within(menu).getByRole('link', { name: /F1 2026/ })).toHaveAttribute('href', '/league/f1-2026/');
  });

  it('marks the champions once the season is over', async () => {
    openF1('/?league=f1-2026', {
      ...f1Payload,
      metadata: { ...f1Payload.metadata, season_status: 'complete' },
      events: [],
      analysis: {
        ...f1Payload.analysis,
        probabilities: {
          max_verstappen: { title: 100, top3: 100 },
          antonelli: { title: 0, top3: 100 },
          russell: { title: 0, top3: 100 },
          tsunoda: { title: 0, top3: 0 },
        },
        constructorProbabilities: { mercedes: { title: 100 }, red_bull: { title: 0 }, rb: { title: 0 } },
      },
    });

    expect(await screen.findByRole('heading', { name: 'Formula 1 World Championship 2026 Final Standings' })).toBeInTheDocument();
    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent("Drivers' championMax Verstappen (VER)");
    expect(screen.queryByRole('heading', { name: 'Next Races' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'All positions' })).not.toBeInTheDocument();
    expect(screen.queryByRole('table', { name: /exact championship position odds/ })).not.toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: /Drivers' standings/ })).queryByText(/100%/)).not.toBeInTheDocument();
    expect(within(tableRows(/Drivers' standings/)[1]).getByText("Drivers' title: yes")).toBeInTheDocument();
    expect(within(tableRows(/Constructors' standings/)[1]).getByText("Constructors' title: yes")).toBeInTheDocument();
  });

  it('uses actual final ranks even when forecast fields are absent or stale', async () => {
    openF1('/?league=f1-2026', {
      ...f1Payload,
      metadata: { ...f1Payload.metadata, season_status: 'complete' },
      analysis: { ...f1Payload.analysis,
        probabilities: { antonelli: { title: 100, top3: 100 } },
        constructorProbabilities: { red_bull: { title: 100 } },
        positions: undefined, constructorPositions: undefined,
      },
    });
    const snapshot = await screen.findByLabelText('Season snapshot');
    expect(snapshot).toHaveTextContent("Drivers' championMax Verstappen (VER)");
    expect(snapshot).toHaveTextContent("Constructors' championMercedes");
    expect(snapshot).not.toHaveTextContent('Next race');
    expect(within(tableRows(/Drivers' standings/)[1]).getByText("Drivers' title: yes")).toBeInTheDocument();
    expect(within(tableRows(/Drivers' standings/)[3]).getByText('Top 3: yes')).toBeInTheDocument();
    expect(within(tableRows(/Constructors' standings/)[1]).getByText("Constructors' title: yes")).toBeInTheDocument();
  });

  it('shows exact points gaps with a named zero baseline', async () => {
    openF1();
    const section = (await screen.findByRole('heading', { name: 'The Points Gap' })).closest('section')!;
    expect(within(section).getByText(/Points behind VER/)).toBeInTheDocument();
    expect(within(section).getByText(/Points behind MER/)).toBeInTheDocument();
    expect(section.querySelector('.f1-gap-plot dd strong')).toHaveTextContent('0');
    expect(section.querySelector('.f1-gap-track > span')).toHaveStyle({ width: '0%' });
  });

  it('shows an error when the payload is malformed', async () => {
    openF1('/?league=f1-2026', { ...f1Payload, constructorStandings: undefined } as unknown as F1Payload);

    expect(await screen.findByRole('heading', { name: 'This league could not load' })).toBeInTheDocument();
  });
});
