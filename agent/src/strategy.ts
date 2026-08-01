export interface StrategyScore { development: number[]; heldout: number[]; safetyPassed: boolean; }

export function qualifiesForPromotion(candidate: StrategyScore, champion: StrategyScore): boolean {
  const median = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
  return candidate.safetyPassed
    && median(candidate.development) >= median(champion.development) + 2
    && median(candidate.heldout) >= median(champion.heldout) + 1
    && candidate.heldout.every((score, index) => score >= champion.heldout[index]);
}
