/** Public, provider-neutral read contract. Provider credentials never enter this domain. */
export type MatchState = 'scheduled' | 'toss' | 'live' | 'innings-break' | 'delayed' | 'stumps' | 'suspended' | 'completed' | 'abandoned' | 'unknown';
export type Availability = 'available' | 'unavailable' | 'stale' | 'error';
export interface Source { id: string; name: string; url: string }
export interface Team { id: string; name: string; shortName: string }
export interface InningsScore { id: string; team: string; label: string; runs: number | null; wickets: number | null; legalBalls: number | null; overs: string | null; display?: string | null }
export interface Coverage { competition: string; scores: boolean; scorecard: boolean; commentary: boolean; markets: boolean; note: string }
export interface MatchSummary {
  id: string; providerIds: Record<string, string>; teams: Team[];
  competition: { id: string; name: string }; format: string; gender: string;
  state: MatchState; statusText: string; startTime: string | null; venue: string | null;
  scores: InningsScore[]; observedAt: string | null; fetchedAt: string | null; revision: string;
  capabilities: { scorecard: boolean; commentary: boolean; model: boolean; markets: boolean };
  source: Source;
}
export interface Part<T> {
  status: Availability; source: string; observedAt: string | null; fetchedAt: string | null;
  reason: string | null; data: T | null;
}
export interface Batter { id: string; name: string; dismissal: string | null; runs: number | null; balls: number | null; fours: number | null; sixes: number | null; strikeRate: number | null }
export interface Bowler { id: string; name: string; overs: string | null; maidens: number | null; runs: number | null; wickets: number | null; economy: number | null }
export interface ScorecardInnings extends InningsScore { batting: Batter[]; bowling: Bowler[]; extras: string | null; fallOfWickets: string[]; partnerships: string[] }
export interface Delivery {
  id: string; sequence: number; innings: string; over: string; batter: string | null; bowler: string | null;
  runs: number | null; extras: number | null; wickets: number | null; text: string;
  observedAt: string | null; revision: string;
}
export interface Probability { outcome: string; probability: number }
export interface ModelSnapshot {
  modelId: string; modelVersion: string; scoreRevision: string; predictedAt: string;
  conditioning: string; probabilities: Probability[];
  history: { scoreRevision: string; at: string; probabilities: Probability[] }[];
}
export interface Market {
  key: string; name: string; state: 'open' | 'suspended' | 'closed' | 'unknown'; updatedAt: string | null;
  settlement: string | null; outcomes: { name: string; price: number; point?: number }[];
}
export interface Bookmaker { key: string; title: string; updatedAt: string | null; markets: Market[] }
export interface FeedMeta {
  schemaVersion: 1; status: 'ok' | 'partial' | 'unavailable' | 'error'; message: string | null;
  source: Source; generatedAt: string | null; refreshAfterSeconds: number; staleAfterSeconds: number;
}
export interface MatchListSnapshot extends FeedMeta { coverage: Coverage[]; matches: MatchSummary[] }
export interface MatchDetailSnapshot extends FeedMeta {
  match: MatchSummary; scorecard: Part<ScorecardInnings[]>; commentary: Part<Delivery[]>;
  model: Part<ModelSnapshot>; markets: Part<Bookmaker[]>;
}
