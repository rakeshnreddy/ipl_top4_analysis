"""Reproducible standard T20 chase research; this is not the season solver.

Run from the repository root:
  venv/bin/python -m live_model.pipeline --cache .cache/cricsheet
Only local archives are read. No network, credentials, or raw delivery exports.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

VERSION = 't20-chase-logistic-2026-10-v1'
CUTOFF = '2026-10-23'
FEATURES = ['runsNeeded', 'ballsRemaining', 'wicketsRemaining', 'requiredRate',
            'targetRate', 'female', 'resourceRate', 'requiredRateSquared',
            'wicketsSquared', 'ballsSquared', 'rateWickets', 'femaleRate', 'femaleTarget']
# These retirements reduce available resources without counting as a wicket.
WICKET_EXCLUSIONS = {'retired hurt', 'retired not out'}


def totals(innings):
    runs = legal = wickets = 0
    for over in innings.get('overs', []):
        for delivery in over.get('deliveries', []):
            runs += delivery['runs']['total']
            extras = delivery.get('extras', {})
            legal += not (extras.get('wides', 0) or extras.get('noballs', 0))
            wickets += sum(w['kind'] not in WICKET_EXCLUSIONS for w in delivery.get('wickets', []))
    return runs, legal, wickets


def extract_match(data, match_id, competition, cutoff=CUTOFF):
    """Return one whole-match record or an explicit exclusion reason.

    Sample initial state and completed six-ball boundaries, excluding terminal
    states. All snapshots of a match share its label and chronological partition.
    """
    info = data.get('info', {})
    dates = info.get('dates', [])
    if len(dates) != 1:
        return None, 'unknown_or_multiday_date'
    try:
        played = date.fromisoformat(dates[0]).isoformat()
    except (ValueError, TypeError):
        return None, 'invalid_date'
    if played > cutoff:
        return None, 'future_date'
    innings = data.get('innings', [])
    if any(i.get('super_over') for i in innings):
        return None, 'super_over'
    if info.get('match_type') != 'T20' or info.get('overs') != 20 or info.get('balls_per_over') != 6:
        return None, 'unsupported_format'
    if info.get('gender') not in ('male', 'female') or info.get('team_type') != 'club':
        return None, 'unsupported_category'
    outcome = info.get('outcome', {})
    teams = info.get('teams', [])
    if outcome.get('result') or outcome.get('method') or outcome.get('winner') not in teams or len(teams) != 2:
        return None, 'no_standard_winner'
    if len(innings) != 2 or innings[0].get('team') == innings[1].get('team'):
        return None, 'incomplete_innings'
    if any(i.get('miscounted_overs') or i.get('absent_hurt') or i.get('penalty_runs') for i in innings):
        return None, 'unsupported_resources'
    if any(w.get('kind') in WICKET_EXCLUSIONS for i in innings for o in i.get('overs', []) for d in o.get('deliveries', []) for w in d.get('wickets', [])):
        return None, 'unsupported_resources'
    first_runs, first_balls, first_wickets = totals(innings[0])
    target = innings[1].get('target', {})
    if target.get('overs') != 20 or target.get('runs') != first_runs + 1:
        return None, 'revised_or_unknown_target'
    if not (first_balls == 120 or first_wickets == 10) or first_balls > 120 or first_wickets > 10:
        return None, 'incomplete_first_innings'
    final_runs, final_balls, final_wickets = totals(innings[1])
    label = int(outcome['winner'] == innings[1].get('team'))
    if final_balls > 120 or final_wickets > 10 or not (
        (label and final_runs >= target['runs']) or
        (not label and final_runs < target['runs'] - 1 and (final_balls == 120 or final_wickets == 10))
    ):
        return None, 'inconsistent_or_incomplete_result'
    state = {'runs': 0, 'legalBalls': 0, 'wickets': 0, 'target': target['runs'], 'gender': info['gender']}
    states = [dict(state)]
    for over in innings[1].get('overs', []):
        for delivery in over.get('deliveries', []):
            state['runs'] += delivery['runs']['total']
            extras = delivery.get('extras', {})
            legal = not (extras.get('wides', 0) or extras.get('noballs', 0))
            state['legalBalls'] += int(legal)
            state['wickets'] += sum(w['kind'] not in WICKET_EXCLUSIONS for w in delivery.get('wickets', []))
            if legal and state['legalBalls'] % 6 == 0 and state['legalBalls'] < 120 and state['wickets'] < 10 and state['runs'] < state['target']:
                states.append(dict(state))
    return {'id': match_id, 'date': played, 'competition': competition,
            'gender': info['gender'], 'outcome': label, 'states': states}, None


def split_matches(records):
    partitions = {'train': [], 'calibration': [], 'test': []}
    seen = set()
    for record in sorted(records, key=lambda r: (r['date'], r['id'])):
        if record['id'] in seen:
            raise ValueError(f"Duplicate match ID: {record['id']}")
        seen.add(record['id'])
        key = 'train' if record['date'] < '2023-01-01' else 'calibration' if record['date'] < '2024-01-01' else 'test'
        partitions[key].append(record)
    return partitions


def features(state):
    needed = state['target'] - state['runs']
    remaining = 120 - state['legalBalls']
    wickets = 10 - state['wickets']
    rate = needed * 6 / remaining
    female = int(state['gender'] == 'female')
    values = {'runsNeeded': needed, 'ballsRemaining': remaining,
              'wicketsRemaining': wickets, 'requiredRate': rate,
              'targetRate': state['target'] / 20, 'female': female,
              'resourceRate': needed / (wickets + 1), 'requiredRateSquared': rate ** 2,
              'wicketsSquared': wickets ** 2, 'ballsSquared': remaining ** 2,
              'rateWickets': rate * wickets, 'femaleRate': female * rate,
              'femaleTarget': female * state['target'] / 20}
    return [values[k] for k in FEATURES]


def matrix(records):
    x, y, weights, meta = [], [], [], []
    for record in records:
        for state in record['states']:
            x.append(features(state)); y.append(record['outcome'])
            weights.append(1 / len(record['states']))
            meta.append({'id': record['id'], 'competition': record['competition'], 'gender': record['gender'],
                         'phase': 'powerplay' if state['legalBalls'] <= 36 else 'middle' if state['legalBalls'] <= 90 else 'death'})
    return np.array(x), np.array(y), np.array(weights), meta


def sigmoid(values):
    return 1 / (1 + np.exp(-np.clip(values, -35, 35)))


def fit_logistic(x, y, weights, l2=.01, max_steps=80):
    """Deterministic weighted Newton fit, normalized to one unit per match."""
    design = np.c_[np.ones(len(x)), x]
    w = weights / weights.sum()
    beta = np.zeros(design.shape[1])
    regularizer = np.eye(len(beta)) * l2
    regularizer[0, 0] = 0
    def loss(b):
        z = design @ b
        return np.sum(w * (np.logaddexp(0, z) - y * z)) + .5 * b @ regularizer @ b
    for _ in range(max_steps):
        p = sigmoid(design @ beta)
        gradient = design.T @ (w * (p - y)) + regularizer @ beta
        hessian = design.T @ ((w * p * (1 - p))[:, None] * design) + regularizer + np.eye(len(beta)) * 1e-10
        step = np.linalg.solve(hessian, gradient)
        alpha = 1.0
        before = loss(beta)
        while alpha > 1e-7 and loss(beta - alpha * step) > before:
            alpha *= .5
        beta -= alpha * step
        if np.max(np.abs(alpha * step)) < 1e-7:
            break
    return beta


def probability_metrics(y, p, weights):
    w = weights / weights.sum()
    p = np.clip(p, 1e-8, 1 - 1e-8)
    bins = []
    ece = 0.0
    for lo in np.arange(0, 1, .1):
        mask = (p >= lo) & (p < lo + .1 if lo < .9 else p <= 1)
        if not mask.any(): continue
        mass = float(w[mask].sum())
        predicted = float(np.average(p[mask], weights=w[mask])); actual = float(np.average(y[mask], weights=w[mask]))
        bins.append({'lower': round(float(lo),1), 'upper': round(float(lo+.1),1), 'snapshots': int(mask.sum()),
                     'weightFraction': mass, 'predicted': predicted, 'observed': actual})
        ece += mass * abs(predicted - actual)
    return {'brier': float(np.sum(w * (p-y)**2)),
            'logLoss': float(-np.sum(w * (y*np.log(p)+(1-y)*np.log(1-p)))),
            'ece10': ece, 'calibrationBins': bins}


def evaluate(records, means, scales, beta, calibration, prior, cells):
    x, y, weights, meta = matrix(records)
    logits = np.c_[np.ones(len(x)), (x-means)/scales] @ beta
    calibrated = sigmoid(calibration[0] + calibration[1] * logits)
    # A declared coarse resource baseline fitted only on training matches.
    resource = []
    for rec in records:
        for state in rec['states']:
            phase = min(state['legalBalls']//30, 3)
            bucket = min(int((state['target']-state['runs'])*6/(120-state['legalBalls'])//3), 8)
            wicket = min(state['wickets']//3, 3)
            resource.append(cells.get(f'{rec["gender"]}:{phase}:{bucket}:{wicket}', prior))
    result = {'matches': len(records), 'snapshots': len(y),
              'model': probability_metrics(y, calibrated, weights),
              'baselines': {'constant50': probability_metrics(y,np.full(len(y),.5),weights),
                            'trainChasePrior': probability_metrics(y,np.full(len(y),prior),weights),
                            'trainResourceBuckets': probability_metrics(y,np.array(resource),weights)}, 'groups': {}}
    for dimension in ['gender','competition','phase']:
        result['groups'][dimension] = {}
        for group in sorted({m[dimension] for m in meta}):
            mask = np.array([m[dimension] == group for m in meta])
            group_result = probability_metrics(y[mask],calibrated[mask],weights[mask])
            group_result.update(matches=len({m['id'] for m in meta if m[dimension] == group}), snapshots=int(mask.sum()))
            group_result['baselineBrier'] = float(np.average((y[mask]-np.array(resource)[mask])**2, weights=weights[mask]))
            result['groups'][dimension][group] = group_result
    return result


def resource_baseline(records, prior):
    cells = {}
    for rec in records:
        for state in rec['states']:
            phase = min(state['legalBalls']//30,3)
            bucket = min(int((state['target']-state['runs'])*6/(120-state['legalBalls'])//3),8)
            wicket = min(state['wickets']//3,3)
            key = f'{rec["gender"]}:{phase}:{bucket}:{wicket}'
            positive, total = cells.get(key, (0.,0.))
            weight = 1/len(rec['states'])
            cells[key] = (positive + rec['outcome']*weight,total+weight)
    return {k: (positive+10*prior)/(total+10) for k,(positive,total) in cells.items()}


def load_archives(cache, cutoff):
    records, rejected, manifest = [], Counter(), []
    seen = set()
    for archive in sorted(Path(cache).glob('*_json.zip')):
        competition = archive.name.removesuffix('_json.zip')
        if competition == 'hnd':
            continue
        manifest.append({'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
        with zipfile.ZipFile(archive) as zipped:
            for name in sorted(zipped.namelist()):
                if not name.endswith('.json'): continue
                match_id = Path(name).stem
                if match_id in seen:
                    rejected['duplicate_match_id'] += 1; continue
                seen.add(match_id)
                try:
                    record, reason = extract_match(json.loads(zipped.read(name)), match_id, competition, cutoff)
                except (KeyError, ValueError, TypeError):
                    reason, record = 'malformed_record', None
                if record: records.append(record)
                else: rejected[reason] += 1
    return records, dict(rejected), manifest


def run(cache, output, cutoff=CUTOFF):
    records, rejected, archives = load_archives(cache, cutoff)
    parts = split_matches(records)
    if any(not p for p in parts.values()):
        raise ValueError('All chronological partitions must contain matches')
    x, y, weights, _ = matrix(parts['train'])
    means = np.average(x, axis=0, weights=weights)
    scales = np.sqrt(np.average((x-means)**2,axis=0,weights=weights)); scales[scales<1e-8] = 1
    beta = fit_logistic((x-means)/scales,y,weights,l2=.002)
    cx, cy, cw, _ = matrix(parts['calibration'])
    calibration = fit_logistic((np.c_[np.ones(len(cx)),(cx-means)/scales] @ beta)[:,None],cy,cw,l2=.001)
    prior = float(np.mean([r['outcome'] for r in parts['train']]))
    cells = resource_baseline(parts['train'], prior)
    evaluation = {k: evaluate(v,means,scales,beta,calibration,prior,cells) for k,v in parts.items()}
    test = evaluation['test']; scores = test['model']; groups = test['groups']
    gates = {
        'minimum500TestMatches': test['matches'] >= 500,
        'beatsConstantAndPriorBrier': scores['brier'] < min(test['baselines'][b]['brier'] for b in ['constant50','trainChasePrior']),
        'beatsResourceBaselineBrier': scores['brier'] < test['baselines']['trainResourceBuckets']['brier'],
        'beatsResourceBaselineLogLoss': scores['logLoss'] < test['baselines']['trainResourceBuckets']['logLoss'],
        'overallCalibrationEceAtMost005': scores['ece10'] <= .05,
        'genderCoverage': all(g in groups['gender'] and groups['gender'][g]['matches'] >= 200 and groups['gender'][g]['ece10'] <= .07 for g in ['male','female']),
        'phaseCalibrationEceAtMost008': all(g['matches'] >= 200 and g['ece10'] <= .08 for g in groups['phase'].values()),
        'independentModelReview': False,
        'liveProviderReplayValidation': False,
    }
    supported = [k for k,v in groups['competition'].items() if v['matches'] >= 100 and v['ece10'] <= .08 and v['brier'] <= v['baselineBrier']]
    partitions = {k: {'matches':len(v),'firstDate':min(r['date'] for r in v),'lastDate':max(r['date'] for r in v),
                      'matchIdsSha256':hashlib.sha256('\n'.join(sorted(r['id'] for r in v)).encode()).hexdigest(),
                      'genders':dict(Counter(r['gender'] for r in v)), 'competitions':dict(Counter(r['competition'] for r in v))} for k,v in parts.items()}
    artifact = {'schemaVersion':1, 'version':VERSION, 'trainingCutoff': '2022-12-31', 'dataCutoff':cutoff,
                'conditioning':'Probability the chasing team wins a standard unreduced 120-ball club T20 without a revised target, conditional on a completed match with a non-tied regulation winner.',
                'release':{'status':'research_only' if not all(gates.values()) else 'released','gates':gates},
                'support':{'format':'T20','innings':2,'scheduledBalls':120,'genders':['male','female'],'competitions':supported,
                           'minimumTestMatchesPerCompetition':100,'maxCompetitionEce':.08,'sampling':'initial state and every six legal balls; terminal states excluded',
                           'inputRequirements':['status=live','scoreRevision','targetRevised=false','interruption=false','superOver=false']},
                'model':{'family':'weighted ridge logistic regression plus chronological Platt calibration','featureNames':FEATURES,
                         'means':means.tolist(),'scales':scales.tolist(),'coefficients':beta.tolist(),
                         'calibration':{'intercept':float(calibration[0]),'slope':float(calibration[1])}},
                'validation':{'testMatches':test['matches'],'testSnapshots':test['snapshots'],
                              'brier':scores['brier'],'logLoss':scores['logLoss'],'ece10':scores['ece10'],
                              'split':'train before 2023; calibrate 2023; untouched test 2024 through data cutoff; whole matches',
                              'partitions':partitions},
                'source':{'name':'Cricsheet JSON','url':'https://cricsheet.org/','license':'Open Data Commons Attribution License (ODC-By)',
                          'licenseUrl':'https://cricsheet.org/using/','archives':archives}}
    report = {'schemaVersion':1,'version':VERSION,'dataCutoff':cutoff,'excludedMatches':rejected,
              'archiveManifest':archives,'partitions':partitions,'evaluation':evaluation,'releaseGates':gates,
              'competitionCandidates':supported,
              'uncertainty':'Snapshots are correlated within matches. Match-balanced scores and counts are descriptive; no independent-delivery standard errors or causal claims.',
              'limits':['Only cached club T20 competitions; no international/associate coverage claim.',
                        'No player strength, venue, team strength, weather or live bookmaker inputs.',
                        'Rain/DLS, revised/missing targets, ties, super overs, shortened matches, injury resource anomalies, miscounted overs and penalties excluded.',
                        'Evaluation is at over boundaries, not every delivery; no live source replay/correction validation yet.',
                        'Performance on unseen competitions, new scoring environments and sparse cohorts is unverified.',
                        'Thresholds were set before evaluation for this candidate; no hyperparameter search or test-driven feature selection. Independent review required.',
                        'A held-out test set becomes development evidence once viewed. Future iterations must use a new holdout before release.']}
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    (output/'candidate.json').write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n')
    (output/'evaluation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'version':VERSION,'partitions':{k:v['matches'] for k,v in partitions.items()},
                      'test':{k:scores[k] for k in ['brier','logLoss','ece10']},'release':artifact['release'],
                      'competitionCandidates':supported},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',default='.cache/cricsheet')
    parser.add_argument('--output',default='live_model')
    parser.add_argument('--cutoff',default=CUTOFF)
    args=parser.parse_args()
    run(args.cache,args.output,args.cutoff)
