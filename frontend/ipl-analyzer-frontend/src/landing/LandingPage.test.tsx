/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Root from '../Root';
import type { LeagueIndex } from '../data/leagues';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import { multiSportIndex } from '../test/sportFixtures';

const index: LeagueIndex = {
  ...multiSportIndex,
  default: 'hub',
  leagues: multiSportIndex.leagues.map((league) =>
    league.id === 'epl-2026-27'
      ? { ...league, status: 'in_progress', started: true, facts: [{ label: 'Title favourite', value: 'ARS 81%' }] }
      : league,
  ),
};

function open(path = '/') {
  window.history.replaceState(null, '', path);
  installFetch(finalPayload, mockManifest, { '/data/leagues.json': index });
  return render(<Root />);
}

describe('LandingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  afterEach(() => {
    document.documentElement.removeAttribute('data-theme');
  });

  it('is the site root, with the biggest live races from the data', async () => {
    open();

    expect(await screen.findByRole('heading', { level: 1, name: /Every title race/ })).toBeInTheDocument();
    const races = screen.getByRole('heading', { name: 'Biggest races right now' }).closest('section')!;
    const epl = within(races).getByRole('link', { name: /Premier League/ });
    expect(epl).toHaveAttribute('href', '/?league=epl-2026-27');
    expect(epl).toHaveTextContent('ARS 81%');
    expect(screen.getByRole('link', { name: /See all 1 live races/ })).toHaveAttribute('href', '/?view=hub');
    await waitFor(() => expect(document.title).toBe('Playoff Pulse: Live Title, Playoff & Relegation Odds Across Sports'));
  });

  it('lists every league under its sport and links to the method on the same page', async () => {
    open();

    const sports = (await screen.findByRole('heading', { name: 'Every League, by Sport' })).closest('section')!;
    expect(within(sports).getByRole('heading', { name: 'Football' })).toBeInTheDocument();
    expect(within(sports).getByRole('heading', { name: 'Cricket' })).toBeInTheDocument();
    expect(within(sports).getByRole('link', { name: /IPL 2026/ })).toHaveAttribute('href', '/?league=ipl-2026');
    expect(screen.getByRole('link', { name: 'How the odds are made' })).toHaveAttribute('href', '/#method');
    expect(screen.getByRole('heading', { name: 'How the Odds Are Made' })).toBeInTheDocument();
  });

  it('switches between light and dark and remembers the choice', async () => {
    open();

    const toggle = await screen.findByRole('button', { name: /Switch to the (dark|light) theme/ });
    const first = toggle.getAttribute('aria-label')!.includes('dark') ? 'dark' : 'light';
    fireEvent.click(toggle);
    expect(document.documentElement).toHaveAttribute('data-theme', first);
    expect(window.localStorage.getItem('pp-theme')).toBe(first);
    const second = first === 'dark' ? 'light' : 'dark';
    fireEvent.click(screen.getByRole('button', { name: `Switch to the ${second} theme` }));
    expect(document.documentElement).toHaveAttribute('data-theme', second);
    expect(window.localStorage.getItem('pp-theme')).toBe(second);
  });
});
