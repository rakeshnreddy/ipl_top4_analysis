/** Research T20 chase inference. No provider data or secrets are consumed here. */
export function featureValues(state) {
  const runsNeeded = state.target - state.runs;
  const ballsRemaining = 120 - state.legalBalls;
  const wicketsRemaining = 10 - state.wickets;
  const requiredRate = runsNeeded * 6 / ballsRemaining;
  const female = Number(state.gender === 'female');
  return {
    runsNeeded, ballsRemaining, wicketsRemaining, requiredRate,
    targetRate: state.target / 20, female,
    resourceRate: runsNeeded / (wicketsRemaining + 1),
    requiredRateSquared: requiredRate ** 2,
    wicketsSquared: wicketsRemaining ** 2, ballsSquared: ballsRemaining ** 2,
    rateWickets: requiredRate * wicketsRemaining,
    femaleRate: female * requiredRate, femaleTarget: female * state.target / 20,
  };
}

const unavailable = reason => ({ status: 'unavailable', reason });
const sigmoid = x => 1 / (1 + Math.exp(-Math.max(-35, Math.min(35, x))));

export function predictChase(state, artifact, { allowResearch = false } = {}) {
  if (!artifact || artifact.schemaVersion !== 1) return unavailable('invalid_model');
  if (artifact.release?.status !== 'released' && !allowResearch) return unavailable('model_not_released');
  if (!state || state.format !== 'T20' || state.innings !== 2 || state.scheduledBalls !== 120) return unavailable('unsupported_format_or_innings');
  if (state.status !== 'live' || typeof state.scoreRevision !== 'string' || !state.scoreRevision) return unavailable('missing_current_score_revision');
  if (state.targetRevised !== false || state.interruption !== false || state.superOver !== false) return unavailable('unsupported_or_unknown_conditions');
  if (!artifact.support?.genders?.includes(state.gender) || !artifact.support?.competitions?.includes(state.competition)) return unavailable('unsupported_cohort');
  if (![state.runs,state.wickets,state.legalBalls,state.target].every(Number.isSafeInteger) || state.runs < 0 || state.wickets < 0 || state.wickets >= 10 || state.legalBalls < 0 || state.legalBalls >= 120 || state.target <= state.runs || state.target < 1) return unavailable('invalid_or_terminal_state');
  const model = artifact.model;
  if (!Array.isArray(model?.featureNames) || !Array.isArray(model.coefficients) || !Array.isArray(model.means) || !Array.isArray(model.scales) || model.coefficients?.length !== model.featureNames.length + 1 || model.means?.length !== model.featureNames.length || model.scales?.length !== model.featureNames.length || ![model.calibration?.intercept,model.calibration?.slope,...model.coefficients,...model.means,...model.scales].every(Number.isFinite) || model.scales.some(x=>x<=0)) return unavailable('invalid_model');
  const values = featureValues(state);
  let logit = model.coefficients[0];
  for (let i=0;i<model.featureNames.length;i++) {
    const value = values[model.featureNames[i]];
    if (!Number.isFinite(value)) return unavailable('unknown_model_feature');
    logit += model.coefficients[i+1] * (value-model.means[i])/model.scales[i];
  }
  const probability = sigmoid(model.calibration.intercept + model.calibration.slope * logit);
  return { status:'available', researchOnly: artifact.release?.status !== 'released',
    modelVersion: artifact.version, inputScoreRevision: state.scoreRevision,
    chasingWinProbability:probability, defendingWinProbability:1-probability,
    conditioning:artifact.conditioning };
}
