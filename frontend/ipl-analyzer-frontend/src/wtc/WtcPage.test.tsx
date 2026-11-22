/// <reference types="vitest/globals" />
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Root from '../Root';
import { finalPayload, installFetch, mockManifest } from '../test/fixtures';
import { wtcComplete, wtcFinalAhead, wtcIndex, wtcJoint, wtcPayload, wtcPreSeason } from '../test/wtcFixtures';
import type { WtcPayload } from './wtcData';

function openWtc(path = '/league/wtc-2025-27/', payload: WtcPayload = wtcPayload) {
  window.history.replaceState(null, '', path);
  installFetch(finalPayload, mockManifest, {
    '/data/leagues.json': wtcIndex,
    '/data/wtc-2025-27.json': payload,
  });
  return render(<Root />);
}

const table = () => screen.getByRole('table', { name: /points table/ });
const rowFor = (team: string) => within(table()).getAllByRole('row').find((row) => within(row).queryByRole('rowheader')?.textContent?.startsWith(team))!;

describe('WtcPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('opens the Test championship page, not the T20 cricket page', async () => {
    openWtc();
    expect(await screen.findByRole('heading', { name: 'World Test Championship 2025-27 Odds' })).toBeInTheDocument();
    expect(screen.getByTestId('wtc-page')).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith('/data/wtc-2025-27.json', { cache: 'no-cache' });
    await waitFor(() => expect(document.title).toMatch(/^WTC 2025-27 Final & Title Odds/));
    expect(screen.getByText('In season', { selector: '.status-pill' })).toBeInTheDocument();
  });

  it('shows the PCT table with deductions, two decimals and the final line', async () => {
    openWtc();
    await screen.findByTestId('wtc-page');
    const headers = within(table()).getAllByRole('columnheader').map((cell) => cell.textContent);
    expect(headers).toEqual(['#', 'Team', 'M', 'W', 'L', 'D', 'Ded', 'Pts', 'PCT', 'Final', 'Title']);
    const sa = rowFor('SA');
    expect(sa).toHaveTextContent('66.67');
    expect(sa).toHaveClass('zone-top');
    const aus = rowFor('AUS');
    // 3 points off for a slow over rate, shown as a deduction and in the points.
    expect(within(aus).getByText('−3')).toBeInTheDocument();
    expect(aus).toHaveTextContent('4.17');
    expect(aus).toHaveClass('wtc-cut');
    // 0.00 is a real PCT; an eliminated team is "Out", not a simulated 0%.
    const eng = rowFor('ENG');
    expect(eng).toHaveTextContent('0.00');
    expect(within(eng).getAllByText('Out')).toHaveLength(2);
    // Never 100% for an estimate, and a chance still alive is never shown as nothing.
    expect(table()).not.toHaveTextContent('100%');
    expect(screen.getByText('Over-rate deductions: 3 points')).toBeInTheDocument();
    expect(screen.getByText(/IND, ENG are level on 50.00%/)).toBeInTheDocument();
  });

  it('states what each team needs exactly, with level and out cases', async () => {
    openWtc();
    const needs = await screen.findByRole('region', { name: 'What Each Team Needs' }).catch(() => screen.getByRole('heading', { name: 'What Each Team Needs' }).closest('section')!);
    expect(within(needs).getByText('In control')).toBeInTheDocument();
    expect(within(needs).getByText('Level at best')).toBeInTheDocument();
    expect(within(needs).getByText('Out of the race')).toBeInTheDocument();
    expect(within(needs).getByText(/tie-breakers would decide/)).toBeInTheDocument();
    expect(within(needs).getByText('66.67% now · 3 Tests left')).toBeInTheDocument();
  });

  it('selects a team from the table and keeps the canonical address', async () => {
    openWtc();
    await screen.findByTestId('wtc-page');
    const scroll = vi.mocked(window.HTMLElement.prototype.scrollIntoView);
    scroll.mockClear();
    fireEvent.click(within(rowFor('IND')).getByRole('button'));
    await waitFor(() => expect(scroll.mock.contexts.some((element) => (element as HTMLElement).id === 'team')).toBe(true));
    expect(window.location.pathname).toBe('/league/wtc-2025-27/');
    expect(window.location.hash).toBe('#team=IND');
    expect(screen.getByRole('heading', { level: 2, name: 'India' })).toBeInTheDocument();
    const panel = screen.getByRole('complementary', { name: 'India' });
    expect(within(panel).getByText('Level at best')).toBeInTheDocument();
    expect(within(panel).getByLabelText('Win 60%, draw 15%, lose 25%')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: "India's series" }));
    const series = screen.getByRole('heading', { name: 'Series by Series' }).closest('section')!;
    expect(within(series).queryByText(/South Africa tour of England/)).not.toBeInTheDocument();
    expect(within(series).getByText(/England tour of India/)).toBeInTheDocument();
  });

  it('opens a team from a #team link on the legacy query address', async () => {
    openWtc('/?league=wtc-2025-27#team=aus');
    expect(await screen.findByRole('heading', { level: 2, name: 'Australia' })).toBeInTheDocument();
    for (const link of within(screen.getByRole('navigation', { name: 'Page sections' })).getAllByRole('link')) {
      expect(link.getAttribute('href')).toMatch(/^\/\?league=wtc-2025-27#[a-z]+$/);
    }
    const needLink = screen.getAllByRole('link').find((link) => link.getAttribute('href')?.endsWith('#team=ENG'))!;
    expect(needLink.getAttribute('href')).toBe('/?league=wtc-2025-27#team=ENG');
  });

  it('shows every Test state: under way, cancelled, neutral, month only, abandoned', async () => {
    openWtc();
    await screen.findByTestId('wtc-page');
    expect(screen.getByText('Under way: Day 3: Stumps')).toBeInTheDocument();
    expect(screen.getByText('Cancelled · not counted')).toBeInTheDocument();
    expect(screen.getByText(/neutral ground in UAE/)).toBeInTheDocument();
    expect(screen.getAllByText(/Feb 2027, date to be set/).length).toBeGreaterThan(0);
    expect(screen.getByText('Abandoned · a draw')).toBeInTheDocument();
    expect(screen.getByText('SA won by 214 runs')).toBeInTheDocument();
    expect(screen.getByText('AUS −3 for slow over rate')).toBeInTheDocument();
    expect(screen.getByText(/2 Tests \(1 not counted\)/)).toBeInTheDocument();
    // The swing Test names the team it moves and the size of the move.
    expect(screen.getByText('30.0 pp')).toBeInTheDocument();
    expect(screen.getByText("AUS's chance of reaching the final after each result")).toBeInTheDocument();
  });

  it('shows the final odds with the joint-champion draw once the table is settled', async () => {
    openWtc('/league/wtc-2025-27/', wtcFinalAhead);
    expect(await screen.findByText('Final ahead', { selector: '.status-pill' })).toBeInTheDocument();
    const final = screen.getByRole('heading', { name: 'The Final' }).closest('section')!;
    expect(within(final).getByText('SA v IND')).toBeInTheDocument();
    expect(within(final).getByText('Draw: joint champions')).toBeInTheDocument();
    expect(within(final).getByText('Draw: joint champions').closest('div')).toHaveTextContent('9%');
    expect(within(final).getByText(/A drawn, tied or abandoned final makes both teams joint champions/)).toBeInTheDocument();
    expect(within(rowFor('SA')).getByText('Through')).toBeInTheDocument();
  });

  it('says when the final is under way', async () => {
    openWtc('/league/wtc-2025-27/', { ...wtcFinalAhead, final: { ...wtcFinalAhead.final, live: 'Day 2: Stumps' } });
    expect(await screen.findByText(/The final is under way: Day 2: Stumps/)).toBeInTheDocument();
  });

  it('crowns a champion, or joint champions after a drawn final', async () => {
    const { unmount } = openWtc('/league/wtc-2025-27/', wtcComplete);
    expect(await screen.findByRole('heading', { name: 'WTC 2025-27: South Africa Are Champions' })).toBeInTheDocument();
    expect(screen.getByText('South Africa won the final by 5 wickets.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'What Each Team Needs' })).not.toBeInTheDocument();
    unmount();
    openWtc('/league/wtc-2025-27/', wtcJoint);
    expect(await screen.findByRole('heading', { name: 'WTC 2025-27: SA and IND Share the Title' })).toBeInTheDocument();
    expect(screen.getByText(/South Africa and India are joint champions/)).toBeInTheDocument();
    expect(within(rowFor('IND')).getByText('Joint')).toBeInTheDocument();
  });

  it('is found by "Test" and "WTC" in the league picker', async () => {
    openWtc();
    await screen.findByTestId('wtc-page');
    fireEvent.click(screen.getByRole('button', { name: /Leagues: WTC 2025-27/ }));
    const search = screen.getByLabelText('Find a league or sport');
    for (const query of ['Test', 'wtc']) {
      fireEvent.change(search, { target: { value: query } });
      const nav = screen.getByRole('navigation', { name: 'Leagues' });
      expect(within(nav).getByRole('link', { name: /WTC 2025-27/ })).toHaveAttribute('href', '/league/wtc-2025-27/');
    }
    // Each deduction's source is named, not seven identical "ICC" links.
    fireEvent.click(screen.getByText('Over-rate deductions: 3 points'));
    const source = screen.getAllByRole('link', { hidden: true }).find((link) => link.getAttribute('href') === 'https://example.org/icc')!;
    expect(source).toHaveTextContent('ICC release: AUS lose 3 points');
  });

  it('has a designed pre-season state', async () => {
    openWtc('/league/wtc-2025-27/', wtcPreSeason);
    expect(await screen.findByText('Pre-season', { selector: '.status-pill' })).toBeInTheDocument();
    expect(screen.getByText(/Pre-cycle projections/)).toBeInTheDocument();
    expect(rowFor('SA')).toHaveTextContent('–');
  });
});
