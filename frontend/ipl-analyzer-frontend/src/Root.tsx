import { useEffect, useMemo, useState } from 'react';
import App from './App';
import { LoadingState } from './components/PageState';
import { DEFAULT_LEAGUE_ID } from './data/iplData';
import { HUB_ID, hubRequested, leagueIdFromLocation, loadLeagueIndex, sportOf, type LeagueIndex } from './data/leagues';
import HubPage from './hub/HubPage';
import LandingPage from './landing/LandingPage';
import SportPage from './sport/SportPage';

/** Loads the league list, then shows the cricket page or the page for the league's sport. */
function Root() {
  const requestedLeague = useMemo(() => leagueIdFromLocation(), []);
  const wantsHub = useMemo(() => hubRequested(), []);
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
    return <LoadingState />;
  }

  // The root is the landing page; ?view=hub is the full list of live races.
  if (index && !requestedLeague) {
    return wantsHub ? <HubPage index={index} /> : <LandingPage index={index} />;
  }
  const fallback = index?.default && index.default !== HUB_ID ? index.default : DEFAULT_LEAGUE_ID;
  const leagueId = requestedLeague ?? fallback;
  const entry = index?.leagues.find((league) => league.id === leagueId);
  if (entry && sportOf(entry) !== 'cricket') {
    return <SportPage leagueId={leagueId} leagueIndex={index} />;
  }
  return <App leagueId={leagueId} leagueIndex={index} />;
}

export default Root;
