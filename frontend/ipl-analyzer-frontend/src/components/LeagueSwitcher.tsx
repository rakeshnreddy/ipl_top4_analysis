import { hubHref, leagueHref, leaguesBySport, type LeagueIndex } from '../data/leagues';

/** Every published league, grouped by sport; hidden until there is more than one. */
const LeagueSwitcher = ({ currentId, index }: { currentId: string; index: LeagueIndex | null }) => {
  if (!index || index.leagues.length < 2) {
    return null;
  }

  return (
    <nav className="league-switcher" aria-label="Leagues">
      <div className="league-group">
        <span className="league-group-label">Home</span>
        <a href={hubHref(index.default)}>All live races</a>
      </div>
      {leaguesBySport(index).map((group) => (
        <div className="league-group" key={group.sport}>
          <span className="league-group-label">{group.label}</span>
          {group.leagues.map((league) => (
            <a
              aria-current={league.id === currentId ? 'page' : undefined}
              href={leagueHref(league.id, index.default)}
              key={league.id}
              title={league.name}
            >
              {league.shortName} {league.seasonLabel}
              {league.status !== 'complete' && <small>Live</small>}
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
};

export default LeagueSwitcher;
