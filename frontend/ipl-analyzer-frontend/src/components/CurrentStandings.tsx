import React, { useEffect, useState } from 'react';
import { team_full_names, team_styles, TeamStyle } from '../teamStyles'; // Ensure TeamStyle is exported and imported
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

  // Theme-aware default colors
  const defaultTeamStyle: TeamStyle = { 
    bg: 'var(--panel-bg-light)', // Using CSS variable, assuming light mode default
    text: 'var(--text-color-light)' // Using CSS variable
  };

  useEffect(() => {
    setLoading(true);
    fetch(`${import.meta.env.BASE_URL}current_standings.json`)
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
          .sort((a, b) => {
            if (b.Points !== a.Points) {
              return b.Points - a.Points; // Primary sort: Points
            }
            // Add NRR sorting here if available, or wins as secondary
            return b.Wins - a.Wins; // Secondary sort: Wins
          })
          .map((team, index) => ({
            ...team,
            teamFullName: team_full_names[team.teamKey] || team.teamKey,
            pos: index + 1,
          }));
        setStandings(processedStandings);
        setError(null); // Clear any previous errors
      })
      .catch((fetchError) => {
        console.error("Failed to load standings:", fetchError);
        setError(`Failed to load standings data. Please check network or file. (${fetchError.message})`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <p role="status" aria-live="polite">Loading current standings...</p>;
  }

  if (error) {
    return <p role="alert" aria-live="assertive">{error}</p>; // Style via global CSS
  }

  if (standings.length === 0) {
    return <p>No standings data available at the moment.</p>;
  }

  return (
    <div>
      <div className="metadata mb-2 glassy-panel"> {/* Added glassy-panel */}
        {lastUpdated && <p>Last Updated: {new Date(lastUpdated).toLocaleString()}</p>}
        {dataSource && <p>Source: {dataSource}</p>}
      </div>
      <div className="table-responsive glassy-panel"> {/* Added glassy-panel */}
        <table>
          <caption>Current IPL Team Standings</caption>
          <thead>
            <tr>
              <th scope="col">Pos</th>
              <th scope="col">Team</th>
              <th scope="col">Matches</th>
              <th scope="col">Wins</th>
              <th scope="col">Points</th>
              {/* Add NRR header if data becomes available */}
            </tr>
          </thead>
          <tbody>
            {standings.map((team) => {
              const teamStyle = team_styles[team.teamKey] as TeamStyle | undefined;
              const rowStyle = {
                backgroundColor: teamStyle?.bg || defaultTeamStyle.bg,
                color: teamStyle?.text || defaultTeamStyle.text,
                borderLeft: teamStyle?.accent ? `5px solid ${teamStyle.accent}` : 'none', // Example use of accent
              };
              return (
                <tr key={team.teamKey} style={rowStyle}>
                  <td>{team.pos}</td>
                  <td>{team.teamFullName}</td>
                  <td>{team.Matches}</td>
                  <td>{team.Wins}</td>
                  <td>{team.Points}</td>
                  {/* Add NRR data cell if available */}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default CurrentStandings;
