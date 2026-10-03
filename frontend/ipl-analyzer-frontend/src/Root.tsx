import { useEffect, useMemo, useState } from 'react';
import { Flame } from 'lucide-react';
import App from './App';
import { DEFAULT_LEAGUE_ID } from './data/iplData';
import { leagueIdFromLocation, loadLeagueIndex, sportOf, type LeagueIndex } from './data/leagues';
import SportPage from './sport/SportPage';

/** Loads the league list, then shows the cricket page or the page for the league's sport. */
function Root() {
  const requestedLeague = useMemo(() => leagueIdFromLocation(), []);
  const [index, setIndex] = useState<LeagueIndex | null>(null);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    let active = true;
    // The list is optional: without it the page falls back to the default cricket league.
    loadLeagueIndex()
      .then((loaded) => {
        if (active) {
          setIndex(loaded);
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) {
          setSettled(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (!settled) {
    return (
      <main className="pulse-app pulse-center">
        <div className="loading-panel" role="status" aria-live="polite">
          <Flame aria-hidden="true" />
          <span>Loading Playoff Pulse...</span>
        </div>
      </main>
    );
  }

  // The home page shows the list's default league (the newest IPL season); ?league= picks another.
  const leagueId = requestedLeague ?? index?.default ?? DEFAULT_LEAGUE_ID;
  const entry = index?.leagues.find((league) => league.id === leagueId);
  if (entry && sportOf(entry) !== 'cricket') {
    return <SportPage leagueId={leagueId} leagueIndex={index} />;
  }
  return <App leagueId={leagueId} leagueIndex={index} />;
}

export default Root;
