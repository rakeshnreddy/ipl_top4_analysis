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

  it('routes a motorsport league to the F1 page with both championship tables', async () => {
    openF1();

    expect(await screen.findByRole('heading', { name: "F1 Title Odds: Drivers' & Constructors' Championships" })).toBeInTheDocument();
    expect(screen.getByTestId('f1-page')).toBeInTheDocument();

    const drivers = tableRows(/Drivers' standings/);
    expect(drivers).toHaveLength(5);
    expect(drivers[1]).toHaveTextContent('VER');
    expect(drivers[1]).toHaveTextContent('Red Bull Racing');
    expect(drivers[1]).toHaveTextContent('300');
    expect(drivers[1]).toHaveTextContent('54%');
    expect(drivers[1]).toHaveTextContent('99%');
    expect(drivers[4]).toHaveTextContent('TSU');

    const teams = tableRows(/Constructors' standings/);
    expect(teams).toHaveLength(4);
    expect(teams[1]).toHaveTextContent('Mercedes');
    expect(teams[1]).toHaveTextContent('ANT · RUS');
    expect(teams[1]).toHaveTextContent('480');
    expect(teams[1]).toHaveTextContent('80%');

    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent("Drivers' title favouriteVER 54%");
    expect(screen.getByLabelText('Season snapshot')).toHaveTextContent("Constructors' title favouriteMER 80%");
    await waitFor(() => expect(document.title).toBe("F1 2026 Title Odds: Drivers' & Constructors' Championship Chances | Playoff Pulse"));
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/f1-2026.json', { cache: 'no-cache' });
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

  it('keeps the league in section links and the skip link', async () => {
    openF1();

    const sections = await screen.findByRole('navigation', { name: 'Page sections' });
    // The page has <base href="/">: a bare "#constructors" would open the home page instead.
    expect(within(sections).getByRole('link', { name: 'Drivers' })).toHaveAttribute('href', '/?league=f1-2026#drivers');
    expect(within(sections).getByRole('link', { name: 'Constructors' })).toHaveAttribute('href', '/?league=f1-2026#constructors');
    expect(within(sections).getByRole('link', { name: 'Next races' })).toHaveAttribute('href', '/?league=f1-2026#races');
    expect(within(sections).getByRole('link', { name: 'How it works' })).toHaveAttribute('href', '/?league=f1-2026#method');
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '/?league=f1-2026#main');

    fireEvent.click(within(sections).getByRole('link', { name: 'Constructors' }));
    expect(window.location.search).toBe('?league=f1-2026');
  });

  it('lists F1 under Motorsport in the league menu', async () => {
    openF1();

    fireEvent.click(await screen.findByRole('button', { name: /F1 2026/ }));
    const menu = screen.getByRole('navigation', { name: 'Leagues' });
    expect(within(menu).getByText('Motorsport')).toBeInTheDocument();
    expect(within(menu).getByRole('link', { name: /F1 2026/ })).toHaveAttribute('href', '/?league=f1-2026');
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
    expect(within(tableRows(/Drivers' standings/)[1]).getByText("Drivers' title: yes")).toBeInTheDocument();
    expect(within(tableRows(/Constructors' standings/)[1]).getByText("Constructors' title: yes")).toBeInTheDocument();
  });

  it('shows an error when the payload is malformed', async () => {
    openF1('/?league=f1-2026', { ...f1Payload, constructorStandings: undefined } as unknown as F1Payload);

    expect(await screen.findByRole('heading', { name: 'This league could not load' })).toBeInTheDocument();
  });
});
