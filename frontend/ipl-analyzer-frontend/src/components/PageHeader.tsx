import type { ReactNode } from 'react';
import { samePageHref } from '../lib/ui';

export interface KeyFact {
  label: string;
  value: ReactNode;
  testId?: string;
}

export type StatusTone = 'live' | 'playoffs' | 'final' | 'pre-season';

/**
 * The top of every page: where you are, what the page is, and the three or four
 * numbers worth knowing. Kept compact so the table starts within the first screen.
 */
const PageHeader = ({
  crumb,
  title,
  strap,
  status,
  facts = [],
  factsLabel,
  sections = [],
}: {
  crumb?: ReactNode;
  title: ReactNode;
  strap?: ReactNode;
  status?: { label: string; tone: StatusTone };
  facts?: KeyFact[];
  factsLabel?: string;
  sections?: { href: string; label: string }[];
}) => (
  <section className="page-header" aria-labelledby="page-title">
    <div className="page-header-text">
      {(crumb || status) && (
        <p className="page-crumb">
          {crumb}
          {status && <span className={`status-pill status-${status.tone}`}>{status.label}</span>}
        </p>
      )}
      <h1 id="page-title">{title}</h1>
      {strap && <p className="page-strap">{strap}</p>}
    </div>

    {facts.length > 0 && (
      <dl aria-label={factsLabel} className="key-facts">
        {facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd data-testid={fact.testId}>{fact.value}</dd>
          </div>
        ))}
      </dl>
    )}

    {sections.length > 0 && (
      <nav aria-label="Page sections" className="page-sections">
        {sections.map((section) => (
          <a href={section.href.startsWith('#') ? samePageHref(section.href) : section.href} key={section.href}>
            {section.label}
          </a>
        ))}
      </nav>
    )}
  </section>
);

export default PageHeader;
