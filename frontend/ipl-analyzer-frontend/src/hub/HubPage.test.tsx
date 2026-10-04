/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Root from '../Root';
import type { LeagueIndex } from '../data/leagues';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import { multiSportIndex } from '../test/sportFixtures';

const hubIndex: LeagueIndex = {
  ...multiSportIndex,
  default: 'hub',
  ipl: 'ipl-2026',
  leagues: multiSportIndex.leagues.map((league) =>
    league.id === 'epl-2026-27'
      ? { ...league, started: true, facts: [{ label: 'Title favourite', value: 'ARS 81%' }] }
      : { ...league, facts: [{ label: 'Champions', value: league.champion ?? '' }] },
  ),
};

function open(path: string, index: LeagueIndex = hubIndex) {
  window.history.replaceState(null, '', path);
  installFetch(finalPayload, mockManifest, { '/data/leagues.json': index });
  return render(<Root />);
}

describe('HubPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists every live race at ?view=hub', async () => {
    open('/?view=hub');

    expect(await screen.findByRole('heading', { level: 1, name: 'All Live Races' })).toBeInTheDocument();
    const live = screen.getByRole('heading', { name: 'Live Races' }).closest('section')!;
    const card = within(live).getByRole('link', { name: /Premier League 2026-27/ });
    expect(card).toHaveAttribute('href', '/?league=epl-2026-27');
    expect(card).toHaveTextContent('Title favourite');
    expect(card).toHaveTextContent('ARS 81%');
    expect(card).toHaveTextContent('Live');

    const finals = screen.getByRole('heading', { name: 'Final Tables' }).closest('section')!;
    expect(within(finals).getByRole('link', { name: /IPL 2026/ })).toHaveAttribute('href', '/?league=ipl-2026');
    await waitFor(() => expect(document.title).toBe('All Live Races: Title, Playoff & Relegation Odds | Playoff Pulse'));
  });

  it('can be opened while the IPL is the home page', async () => {
    open('/?view=hub', { ...hubIndex, default: 'ipl-2026' });

    expect(await screen.findByTestId('hub-page')).toBeInTheDocument();
  });

  it('marks a league that has not started as pre-season', async () => {
    open('/?view=hub', {
      ...hubIndex,
      leagues: hubIndex.leagues.map((league) => (league.id === 'epl-2026-27' ? { ...league, started: false } : league)),
    });

    const live = (await screen.findByRole('heading', { name: 'Live Races' })).closest('section')!;
    expect(within(live).getByRole('link', { name: /Premier League 2026-27/ })).toHaveTextContent('Pre-season');
  });

  it('links league pages back to the hub', async () => {
    open('/?league=ipl-2026');

    fireEvent.click(await screen.findByRole('button', { name: /^Leagues/ }));
    const nav = screen.getByRole('navigation', { name: 'Leagues' });
    expect(within(nav).getByRole('link', { name: 'All live races' })).toHaveAttribute('href', '/?view=hub');
    // The wordmark goes to the landing page.
    expect(screen.getByRole('link', { name: 'Playoff Pulse' })).toHaveAttribute('href', '/');
  });
});
