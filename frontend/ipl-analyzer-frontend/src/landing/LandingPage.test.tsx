/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Root from '../Root';
import type { LeagueIndex } from '../data/leagues';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import { footballPayload, multiSportIndex } from '../test/sportFixtures';

const index: LeagueIndex = {
  ...multiSportIndex,
  default: 'hub',
  leagues: multiSportIndex.leagues.map((league) =>
    league.id === 'epl-2026-27'
      ? { ...league, status: 'in_progress', started: true, facts: [{ label: 'Title favourite', value: 'ARS 81%' }] }
      : league,
  ),
};

function open(path = '/', seasonIndex = index, feature: unknown = footballPayload) {
  window.history.replaceState(null, '', path);
  installFetch(finalPayload, mockManifest, { '/data/leagues.json': seasonIndex, '/data/epl-2026-27.json': feature });
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

  it('shows numerical title chances from the payload and a direct league destination', async () => {
    open();

    expect(await screen.findByRole('heading', { level: 1, name: /Every race.*In the balance/ })).toBeInTheDocument();
    const feature = await screen.findByRole('link', { name: 'Explore the title race' });
    expect(feature).toHaveAttribute('href', '/league/epl-2026-27/');
    const raceFeature = feature.closest('section')!;
    expect(within(raceFeature).getByText('81%')).toBeInTheDocument();
    expect(raceFeature.querySelector('.landing-feature-track > span')).toHaveStyle({ width: '81.2%' });
    const races = screen.getByRole('heading', { name: 'Featured races' }).closest('section')!;
    const epl = within(races).getByRole('link', { name: /Premier League/ });
    expect(epl).toHaveAttribute('href', '/league/epl-2026-27/');
    expect(epl).toHaveTextContent('ARS 81%');
    expect(screen.getByRole('link', { name: 'Explore the races' })).toHaveAttribute('href', '/?view=hub');
    await waitFor(() => expect(document.title).toBe('Playoff Pulse: Live Title, Playoff & Relegation Odds Across Sports'));
  });

  it('opens sport directories into direct links and explains the cricket model', async () => {
    open();

    const sports = (await screen.findByRole('heading', { name: 'Find your league.' })).closest('section')!;
    expect(within(sports).getByRole('button', { name: /Football/ })).toHaveAttribute('aria-expanded', 'false');
    const cricket = within(sports).getByRole('button', { name: /Cricket/ });
    fireEvent.click(cricket);
    expect(cricket).toHaveAttribute('aria-expanded', 'true');
    expect(within(sports).getByRole('link', { name: /IPL 2026/ })).toHaveAttribute('href', '/league/ipl-2026/');
    expect(screen.getByRole('link', { name: 'How the odds are made' })).toHaveAttribute('href', '/#method');
    expect(screen.getByRole('heading', { name: /The odds have a method/ })).toBeInTheDocument();
    expect(screen.getByText(/Cricket uses equal-strength result scenarios/)).toBeInTheDocument();
  });

  it('keeps tiny tracks exact and near-certainty formatted safely', async () => {
    const feature = structuredClone(footballPayload);
    feature.analysis.probabilities.Arsenal.title = 99.96;
    feature.analysis.probabilities.Liverpool.title = 0.04;
    feature.analysis.probabilities.Chelsea.title = 0;
    open('/', index, feature);
    const race = (await screen.findByRole('link', { name: 'Explore the title race' })).closest('section')!;
    expect(within(race).getByText('>99.9%')).toBeInTheDocument();
    expect(race.querySelector('.landing-contender-track > span')).toHaveStyle({ width: '0.04%' });
    expect(race.querySelectorAll('.landing-contender-track > span')[1]).toHaveStyle({ width: '0%' });
  });

  it('features multiple sports before a second league from one sport and labels preseason honestly', async () => {
    const epl = index.leagues[0];
    const expanded: LeagueIndex = { ...index, leagues: [
      epl,
      { ...epl, id: 'la-liga-2026-27', shortName: 'La Liga' },
      { ...epl, id: 'bundesliga-2026-27', shortName: 'Bundesliga' },
      { ...epl, id: 'nba-2026-27', sport: 'basketball', shortName: 'NBA', started: false },
      { ...epl, id: 'f1-2026', sport: 'motorsport', shortName: 'F1' },
    ] };
    open('/', expanded);
    const races = (await screen.findByRole('heading', { name: 'Featured races' })).closest('section')!;
    const links = within(races).getAllByRole('link');
    expect(links[0]).toHaveTextContent('Premier League');
    expect(links[1]).toHaveTextContent('NBA');
    expect(links[2]).toHaveTextContent('F1');
    expect(links[1]).toHaveTextContent('Pre-season');
    expect(within(races).getByText('4 seasons in progress · 1 upcoming')).toBeInTheDocument();
  });

  it('keeps direct access when the extra preview payload is malformed', async () => {
    open('/', index, { analysis: { probabilities: {} } });
    expect(await screen.findByRole('link', { name: 'Explore this season' })).toHaveAttribute('href', '/league/epl-2026-27/');
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(screen.queryByText('0–100% scale')).not.toBeInTheDocument();
  });

  it('keeps source warnings beside the hero forecast instead of hiding provenance', async () => {
    open('/', index, { ...footballPayload, metadata: { ...footballPayload.metadata, warnings: ['A scheduled result is missing from the source.'] } });
    const note = await screen.findByText('Data notes (1)');
    fireEvent.click(note);
    expect(screen.getByText('A scheduled result is missing from the source.')).toBeVisible();
  });

  it('switches between light and dark and remembers the choice', async () => {
    open();

    const toggle = await screen.findByRole('button', { name: 'Dark theme' });
    const first = toggle.getAttribute('aria-pressed') === 'true' ? 'light' : 'dark';
    fireEvent.click(toggle);
    expect(document.documentElement).toHaveAttribute('data-theme', first);
    expect(window.localStorage.getItem('pp-theme')).toBe(first);
    const second = first === 'dark' ? 'light' : 'dark';
    fireEvent.click(screen.getByRole('button', { name: 'Dark theme' }));
    expect(document.documentElement).toHaveAttribute('data-theme', second);
    expect(window.localStorage.getItem('pp-theme')).toBe(second);
  });

  it('filters the league picker and restores focus on Escape', async () => {
    open();
    const menu = await screen.findByRole('button', { name: 'Leagues' });
    fireEvent.click(menu);
    const search = screen.getByRole('searchbox', { name: 'Find a league or sport' });
    expect(search).toHaveFocus();
    fireEvent.change(search, { target: { value: 'zzzz-no-league' } });
    expect(screen.getByRole('status')).toHaveTextContent('No leagues match');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(menu).toHaveFocus();
    expect(menu).toHaveAttribute('aria-expanded', 'false');
  });
});
