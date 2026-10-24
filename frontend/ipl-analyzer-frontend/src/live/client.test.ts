import { describe, expect, it } from 'vitest';
import { apiOrigin, parseDetailSnapshot, parseListSnapshot } from './client';
import { listFixture, detailFixture } from './testFixtures';
describe('live cricket network boundary', () => {
  it('allows HTTPS origins and local development only, never credentials or endpoint paths', () => {
    expect(apiOrigin('https://scores.example.test')).toBe('https://scores.example.test');
    for (const input of ['https://user:key@scores.test', 'https://scores.test/key', 'javascript:alert(1)', 'http://scores.test', 'https://scores.test/?key=secret']) expect(apiOrigin(input)).toBeNull();
    expect(apiOrigin('http://localhost:8787')).toBe('http://localhost:8787');
  });
  it('rejects malformed nested values rather than rendering invented scores or probabilities', () => {
    expect(parseListSnapshot(listFixture())).toEqual(listFixture());
    expect(parseDetailSnapshot(detailFixture(), 'synthetic-one')).toEqual(detailFixture());
    const bad = detailFixture();
    bad.model = { status: 'available', source: 'Test model', observedAt: bad.match.observedAt, fetchedAt: bad.match.fetchedAt, reason: null, data: { modelId: 'test', modelVersion: 'test', scoreRevision: bad.match.revision, predictedAt: bad.match.observedAt!, conditioning: 'Synthetic test', probabilities: [{ outcome: 'A', probability: 1.2 }], history: [] } };
    expect(() => parseDetailSnapshot(bad, 'synthetic-one')).toThrow(/invalid/i);
    expect(() => parseDetailSnapshot(detailFixture(), 'different-match')).toThrow(/match/i);
    const invalidDisplay = listFixture();
    invalidDisplay.matches[0].scores[0].display = { score: '100/2' } as unknown as string;
    expect(() => parseListSnapshot(invalidDisplay)).toThrow(/invalid/i);
    const broken = listFixture(); broken.matches[0].scores[0].runs = '99' as unknown as number;
    expect(() => parseListSnapshot(broken)).toThrow(/invalid/i);
  });
});
