import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SponsorshipNotice from './SponsorshipNotice';
import { monetizationFromEnv, type CommercialContext } from '../lib/monetization';

const context: CommercialContext = {
  url: 'https://ipl-playoff-pulse.pages.dev/cricket/',
  sourceIds: ['sportscore'], contentReady: true, attributionVisible: true,
};
const supplied = monetizationFromEnv({
  VITE_SPONSOR_NAME: 'Supplied sports journal',
  VITE_SPONSOR_URL: 'https://sponsor.example/campaign',
  VITE_SPONSOR_MESSAGE: 'Read the supplied campaign message.',
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); });

describe('SponsorshipNotice', () => {
  it('renders only the supplied campaign with visible advertising disclosure and a sponsored link', () => {
    render(<SponsorshipNotice config={supplied} context={context} />);
    const notice = screen.getByRole('complementary', { name: 'Advertisement' });
    expect(notice).toHaveTextContent('Advertisement');
    expect(notice).toHaveTextContent('Read the supplied campaign message.');
    const link = screen.getByRole('link', { name: 'Supplied sports journal' });
    expect(link).toHaveAttribute('href', 'https://sponsor.example/campaign');
    expect(link).toHaveAttribute('rel', 'sponsored noopener noreferrer');
    expect(link).toHaveAttribute('target', '_blank');
    expect(notice.querySelectorAll('a')).toHaveLength(1);
    expect(notice.querySelector('iframe, img, script')).toBeNull();
  });

  it('renders no placeholder for a missing campaign or an ineligible source, host or content state', () => {
    for (const testContext of [
      { ...context, sourceIds: ['sportscore', 'cricketdata'] },
      { ...context, sourceIds: [] },
      { ...context, url: 'https://rakeshnreddy.github.io/ipl_top4_analysis/cricket/' },
      { ...context, url: 'https://ipl-playoff-pulse.pages.dev/league/f1-2026/' },
      { ...context, contentReady: false },
      { ...context, attributionVisible: false },
    ]) {
      const { container, unmount } = render(<SponsorshipNotice config={supplied} context={testContext} />);
      expect(container).toBeEmptyDOMElement();
      unmount();
    }
    const { container } = render(<SponsorshipNotice config={monetizationFromEnv()} context={context} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('reads optional public campaign settings and displays campaign text safely', () => {
    vi.stubEnv('VITE_SPONSOR_NAME', 'Named <img src=x onerror=alert(1)> sponsor');
    vi.stubEnv('VITE_SPONSOR_URL', 'https://sponsor.example/supplied');
    vi.stubEnv('VITE_SPONSOR_MESSAGE', 'A <script>alert(1)</script> message.');
    const { container } = render(<SponsorshipNotice context={context} />);
    expect(screen.getByRole('link')).toHaveTextContent('Named <img src=x onerror=alert(1)> sponsor');
    expect(container).toHaveTextContent('A <script>alert(1)</script> message.');
    expect(container.querySelector('img, script')).toBeNull();
  });
});
