import React, { useEffect, useState } from 'react';
import { team_full_names, team_styles, full_name_key_mapping } from '../teamStyles';

interface TeamStats {
  Matches: number;
  Wins: number;
  Points: number;
}

interface StandingsData {
  [key: string]: TeamStats;
}

interface FetchedData {
  last_updated: string;
  source: string;
  standings: StandingsData;
}

interface StandingRow extends TeamStats {
  teamKey: string;
  teamFullName: string;
  pos: number;
}

const CurrentStandings: React.FC = () => {
  const [standings, setStandings] = useState<StandingRow[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [dataSource, setDataSource] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/current_standings.json')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((data: FetchedData) => {
        setLastUpdated(data.last_updated);
        setDataSource(data.source);

        const processedStandings = Object.entries(data.standings)
          .map(([key, stats]) => ({
            teamKey: key,
            ...stats,
          }))
          .sort((a, b) => b.Points - a.Points) // Sort by points descending
          .map((team, index) => ({
            ...team,
            teamFullName: team_full_names[team.teamKey] || team.teamKey,
            pos: index + 1,
          }));
        setStandings(processedStandings);
        setLoading(false);
      })
      .catch((fetchError) => {
        console.error("Failed to load standings:", fetchError);
        setError(`Failed to load standings data. ${fetchError.message}`);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <p>Loading standings...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      <div style={{ marginBottom: '10px', fontSize: '0.9em', color: '#555' }}>
        <p>Last Updated: {lastUpdated ? new Date(lastUpdated).toLocaleString() : 'N/A'}</p>
        <p>Source: {dataSource || 'N/A'}</p>
      </div>
      <table>
        <thead>
          <tr>
            <th>Pos</th>
            <th>Team</th>
            <th>Matches</th>
            <th>Wins</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {standings.map((team) => {
            const style = team_styles[team.teamKey] || {};
            return (
              <tr key={team.teamKey} style={{ backgroundColor: style.bg, color: style.text }}>
                <td>{team.pos}</td>
                <td>{team.teamFullName}</td>
                <td>{team.Matches}</td>
                <td>{team.Wins}</td>
                <td>{team.Points}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default CurrentStandings;
