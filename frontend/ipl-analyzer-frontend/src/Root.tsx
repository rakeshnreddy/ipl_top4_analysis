import { Component, lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react';
import './App.css';
import { ErrorState, LoadingState } from './components/PageState';
import { DEFAULT_LEAGUE_ID } from './data/iplData';
import { HUB_ID, hubRequested, leagueIdFromLocation, loadLeagueIndex, sportOf, type LeagueIndex } from './data/leagues';
const App = lazy(() => import('./App'));
const F1Page = lazy(() => import('./f1/F1Page'));
const HubPage = lazy(() => import('./hub/HubPage'));
const LandingPage = lazy(() => import('./landing/LandingPage'));
const SportPage = lazy(() => import('./sport/SportPage'));

/** Loads the league list, then shows the cricket page or the page for the league's sport. */
function Root() {
  const requestedLeague = useMemo(() => leagueIdFromLocation(), []);
  const wantsHub = useMemo(() => hubRequested(), []);
  const [index, setIndex] = useState<LeagueIndex | null>(null);
  const [settled, setSettled] = useState(false);
  const sport = index?.leagues.find((league) => league.id === requestedLeague)?.sport ?? '';

  useEffect(() => {
    document.documentElement.dataset.sport = sport;
  }, [sport]);

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
  if (entry && sportOf(entry) === 'motorsport') {
    return <F1Page leagueId={leagueId} leagueIndex={index} />;
  }
  if (entry && sportOf(entry) !== 'cricket') {
    return <SportPage leagueId={leagueId} leagueIndex={index} />;
  }
  return <App leagueId={leagueId} leagueIndex={index} />;
}

/** A stale/offline deployment chunk must offer recovery instead of a blank page. */
class RouteBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? <ErrorState title="This page could not load" message="A connection or site update interrupted the page. Reload to try again." onRetry={() => window.location.reload()} />
      : this.props.children;
  }
}
const RoutedRoot = () => <RouteBoundary><Suspense fallback={<LoadingState />}><Root /></Suspense></RouteBoundary>;
export default RoutedRoot;
