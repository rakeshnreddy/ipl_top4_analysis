import { useEffect, useId, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { hubHref, isLive, leagueHref, leaguesBySport, statusLabel, type LeagueIndex } from '../data/leagues';

/** The brand mark: a single pulse line. */
const PulseMark = () => (
  <svg aria-hidden="true" className="pulse-mark" focusable="false" height="22" viewBox="0 0 24 24" width="22">
    <path
      d="M2 12.5h4.2l2.3-6 4.4 11.5 2.6-7.5H22"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2.4"
    />
  </svg>
);

/**
 * Site-wide header: the wordmark links home, and one menu lists every league by sport.
 * Replaces the rows of league chips that used to sit above every page.
 */
const SiteHeader = ({ index, currentId, currentLabel }: { index: LeagueIndex | null; currentId?: string; currentLabel?: string }) => {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const menuRef = useRef<HTMLDivElement>(null);
  const home = hubHref(index?.default ?? 'hub');
  // Sports with the most live races first; the sort is stable, so ties keep the list's order.
  const groups = index
    ? leaguesBySport(index).sort((a, b) => b.leagues.filter(isLive).length - a.leagues.filter(isLive).length)
    : [];

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    const onPointer = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onPointer);
    };
  }, [open]);

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <a className="wordmark" href={home}>
          <PulseMark />
          <span>Playoff Pulse</span>
        </a>

        {index && index.leagues.length > 0 && (
          <div className="league-menu" ref={menuRef}>
            <button
              aria-controls={panelId}
              aria-expanded={open}
              className="league-menu-button"
              onClick={() => setOpen((value) => !value)}
              type="button"
            >
              <span>
                {currentLabel && <span className="visually-hidden">Leagues: </span>}
                {currentLabel ?? 'Leagues'}
              </span>
              <ChevronDown aria-hidden="true" size={16} />
            </button>

            <div className="league-menu-panel" hidden={!open} id={panelId}>
              <nav aria-label="Leagues">
                <a className="league-menu-home" href={home}>
                  All live races
                </a>
                <div className="league-menu-groups">
                  {groups.map((group) => (
                    <div className="league-menu-group" key={group.sport}>
                      <p className="label">{group.label}</p>
                      <ul>
                        {group.leagues.map((league) => (
                          <li key={league.id}>
                            <a
                              aria-current={league.id === currentId ? 'page' : undefined}
                              href={leagueHref(league.id, index.default)}
                              title={league.name}
                            >
                              <span>
                                {league.shortName} {league.seasonLabel}
                              </span>
                              <small className={`status-text status-${statusLabel(league).toLowerCase()}`}>
                                {statusLabel(league)}
                              </small>
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </nav>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default SiteHeader;
