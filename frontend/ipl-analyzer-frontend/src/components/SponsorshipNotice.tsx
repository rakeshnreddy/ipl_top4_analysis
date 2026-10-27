import { monetizationFromEnv, sponsorshipFor, type CommercialContext, type MonetizationConfig } from '../lib/monetization';
import './SponsorshipNotice.css';

export interface SponsorshipNoticeProps { context: CommercialContext; config?: MonetizationConfig }

/** A supplied direct campaign only. The caller also owns current-page freshness gates. */
export default function SponsorshipNotice({ context, config = monetizationFromEnv(import.meta.env) }: SponsorshipNoticeProps) {
  const campaign = sponsorshipFor(config, context);
  if (!campaign) return null;
  return <aside className="sponsorship-notice" aria-label={campaign.disclosure}>
    <span className="sponsorship-disclosure">{campaign.disclosure}</span>
    <a className="sponsorship-name" href={campaign.url} rel={campaign.rel} target="_blank" title="Opens in a new tab">{campaign.name}</a>
    <p className="sponsorship-message">{campaign.message}</p>
  </aside>;
}
