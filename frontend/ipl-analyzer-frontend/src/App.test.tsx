/// <reference types="vitest/globals" />
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { IplSeasonPayload } from './data/iplData';

const standings: IplSeasonPayload['standings'] = [
  { teamKey: 'Punjab', shortName: 'PBKS', fullName: 'Punjab Kings', matches: 8, wins: 6, losses: 1, noResult: 1, points: 13, nrr: 1.043, rank: 1, remainingMatches: 6 },
  { teamKey: 'Hyderabad', shortName: 'SRH', fullName: 'Sunrisers Hyderabad', matches: 9, wins: 6, losses: 3, noResult: 0, points: 12, nrr: 0.832, rank: 3, remainingMatches: 5 },
  { teamKey: 'Bangalore', shortName: 'RCB', fullName: 'Royal Challengers Bengaluru', matches: 9, wins: 6, losses: 3, noResult: 0, points: 12, nrr: 1.42, rank: 2, remainingMatches: 5 },
  { teamKey: 'Rajasthan', shortName: 'RR', fullName: 'Rajasthan Royals', matches: 10, wins: 6, losses: 4, noResult: 0, points: 12, nrr: 0.51, rank: 4, remainingMatches: 4 },
  { teamKey: 'Gujarat', shortName: 'GT', fullName: 'Gujarat Titans', matches: 9, wins: 5, losses: 4, noResult: 0, points: 10, nrr: -0.192, rank: 5, remainingMatches: 5 },
  { teamKey: 'Delhi', shortName: 'DC', fullName: 'Delhi Capitals', matches: 9, wins: 4, losses: 5, noResult: 0, points: 8, nrr: -0.895, rank: 6, remainingMatches: 5 },
  { teamKey: 'Chennai', shortName: 'CSK', fullName: 'Chennai Super Kings', matches: 8, wins: 3, losses: 5, noResult: 0, points: 6, nrr: -0.121, rank: 7, remainingMatches: 6 },
  { teamKey: 'Kolkata', shortName: 'KKR', fullName: 'Kolkata Knight Riders', matches: 8, wins: 2, losses: 5, noResult: 1, points: 5, nrr: -0.751, rank: 8, remainingMatches: 6 },
  { teamKey: 'Mumbai', shortName: 'MI', fullName: 'Mumbai Indians', matches: 8, wins: 2, losses: 6, noResult: 0, points: 4, nrr: -0.784, rank: 9, remainingMatches: 6 },
  { teamKey: 'Lucknow', shortName: 'LSG', fullName: 'Lucknow Super Giants', matches: 8, wins: 2, losses: 6, noResult: 0, points: 4, nrr: -1.106, rank: 10, remainingMatches: 6 },
];

const mockPayload: IplSeasonPayload = {
  metadata: {
    season: 2026,
    generated_at: '2026-05-01T21:13:08Z',
    source: 'Cricbuzz',
    source_url: 'https://www.cricbuzz.com/cricket-series/9241/indian-premier-league-2026/points-table',
    data_freshness_status: 'warning',
    warnings: ['Fixture feed appears partial: found 1 scheduled match(es), but standings imply about 27 league match(es) remaining.'],
  },
  standings,
  fixtures: [
    {
      id: 'cricbuzz-44',
      matchNo: 44,
      teamA: 'Chennai',
      teamB: 'Mumbai',
      dateTimeGMT: '2026-05-02T14:00:00Z',
      dateTimeLocal: 'Tomorrow , 7:30 PM LOCAL',
      venue: 'MA Chidambaram Stadium, Chennai',
      status: 'scheduled',
      sourceUrl: 'https://www.cricbuzz.com/live-cricket-scores/151987/csk-vs-mi-44th-match-ipl-2026',
    },
  ],
  analysis: {
    method: 'Exhaustive',
    simulationCount: 2,
    generatedAt: '2026-05-01T21:13:08Z',
    overallProbabilities: Object.fromEntries(
      standings.map((team) => [team.teamKey, { top4: team.rank <= 4 ? 100 : 0, top2: team.rank <= 2 ? 100 : 0 }]),
    ),
    teamAnalysis: { '4': {}, '2': {} },
    qualificationPath: {
      '4': Object.fromEntries(standings.map((team) => [team.teamKey, { possible: 0, guaranteed: null, target_matches: team.remainingMatches, method: 'Exhaustive' }])),
      '2': Object.fromEntries(standings.map((team) => [team.teamKey, { possible: 0, guaranteed: null, target_matches: team.remainingMatches, method: 'Exhaustive' }])),
    },
  },
};

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockPayload,
    } as Response);
  });

  it('loads the canonical payload and renders the playoff pulse surface', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'IPL Playoff Pulse' })).toBeInTheDocument();
    expect(screen.getByTestId('freshness-warning')).toHaveTextContent('Fixture feed appears partial');
    expect(screen.getByText('Royal Challengers Bengaluru')).toBeInTheDocument();
    expect(screen.getAllByText('CSK').length).toBeGreaterThan(0);
    expect(screen.getAllByText('MI').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Top 4 Odds' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /caption/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /png/i })).toBeInTheDocument();
    expect(screen.queryByTestId('share-lab')).not.toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith('/ipl_top4_analysis/data/ipl-2026.json', { cache: 'no-cache' });
  });

  it('sorts the standings by points, then NRR, then wins', async () => {
    const { container } = render(<App />);
    await screen.findByTestId('standings-ladder');

    const rows = Array.from(container.querySelectorAll('.standing-row')).map((row) => row.textContent || '');

    expect(rows[0]).toContain('PBKS');
    expect(rows[1]).toContain('RCB');
    expect(rows[2]).toContain('SRH');
  });
});
