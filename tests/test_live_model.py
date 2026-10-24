"""Integrity and inference tests for the independent, research-only T20 chase model."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.find_spec('live_model.pipeline')
if SPEC:
    from live_model import pipeline as model
else:
    model = None


def match_fixture():
    def delivery(runs=0, extras=None, wickets=None):
        d = {'runs': {'total': runs, 'batter': runs, 'extras': 0}}
        if extras: d['extras'] = extras
        if wickets: d['wickets'] = [{'kind': kind} for kind in wickets]
        return d
    first = [delivery(1) for _ in range(120)]
    second = [delivery(1) for _ in range(120)] + [delivery(1)]
    # End a valid chase on the first ball of its last over, with a wide first.
    second = [delivery(2, {'wides': 2})] + [delivery(2) for _ in range(60)]
    return {'info': {'dates': ['2024-04-01'], 'balls_per_over': 6,
                     'overs': 20, 'match_type': 'T20', 'gender': 'female',
                     'teams': ['A', 'B'], 'team_type': 'club',
                     'outcome': {'winner': 'B', 'by': {'wickets': 10}}},
            'innings': [{'team': 'A', 'overs': [{'over': i // 6, 'deliveries': first[i:i+6]} for i in range(0,120,6)]},
                        {'team': 'B', 'target': {'overs': 20, 'runs': 121},
                         'overs': [{'over': 0, 'deliveries': second}]}]}


class LiveModelTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(model, 'The independent T20 model module must exist')

    def test_legal_balls_and_targets_are_not_decimal_overs(self):
        record, reason = model.extract_match(match_fixture(), 'wpl:1', 'wpl', '2026-10-23')
        self.assertIsNone(reason)
        self.assertEqual(record['states'][0]['legalBalls'], 0)
        # Illegal deliveries change runs but do not advance legal balls.
        self.assertEqual(record['states'][1]['legalBalls'], 6)
        self.assertEqual(record['states'][1]['runs'], 14)
        self.assertTrue(all(s['target'] == 121 for s in record['states']))
        self.assertTrue(all(s['runs'] < 121 for s in record['states']))
        self.assertEqual(record['outcome'], 1)

    def test_revised_targets_and_future_dates_are_rejected(self):
        data = match_fixture(); data['innings'][1]['target']['runs'] = 100
        self.assertEqual(model.extract_match(data, '1', 'wpl', '2026-10-23')[1], 'revised_or_unknown_target')
        data = match_fixture(); data['info']['dates'] = ['2026-10-24']
        self.assertEqual(model.extract_match(data, '1', 'wpl', '2026-10-23')[1], 'future_date')

    def test_super_over_tie_and_uncounted_resources_are_rejected(self):
        for mutate, reason in [
            (lambda d: d['innings'].append({'super_over': True}), 'super_over'),
            (lambda d: d['info'].update(outcome={'result': 'tie'}), 'no_standard_winner'),
            (lambda d: d['innings'][1].update(absent_hurt=['Batter']), 'unsupported_resources'),
            (lambda d: d['innings'][1].update(miscounted_overs={'1': {'balls': 7}}), 'unsupported_resources'),
        ]:
            d = match_fixture(); mutate(d)
            self.assertEqual(model.extract_match(d, '1', 'wpl', '2026-10-23')[1], reason)

    def test_chronological_split_never_leaks_a_match(self):
        records = [{'id': str(i), 'date': d} for i, d in enumerate(['2022-12-31','2023-01-01','2023-12-31','2024-01-01'])]
        parts = model.split_matches(records)
        self.assertEqual([[m['id'] for m in parts[k]] for k in ['train','calibration','test']], [['0'],['1','2'],['3']])
        self.assertEqual(len(set().union(*[{m['id'] for m in a} for a in parts.values()])), 4)

    def test_logistic_fit_learns_signal_with_finite_calibrated_scores(self):
        x = np.array([[-2],[-1],[-.5],[.5],[1],[2]], dtype=float)
        y = np.array([0,0,0,1,1,1], dtype=float)
        beta = model.fit_logistic(x,y,np.ones(6), l2=.01)
        p = model.sigmoid(np.c_[np.ones(6),x] @ beta)
        self.assertTrue(np.all(np.isfinite(p)))
        self.assertGreater(p[-1], .9)
        self.assertLess(p[0], .1)
        metrics = model.probability_metrics(y,p,np.ones(6))
        self.assertLess(metrics['brier'], .1)
        self.assertLess(metrics['logLoss'], .3)

    def test_inference_contract_suppresses_unreleased_and_invalid_states(self):
        script = r"""
import { predictChase } from './live_model/inference.mjs';
const artifact = {schemaVersion:1, release:{status:'research_only'}, support:{competitions:['wpl'], genders:['female']}, model:{featureNames:['runsNeeded'], means:[60], scales:[20], coefficients:[0,-1], calibration:{intercept:0,slope:1}}};
const state = {format:'T20', innings:2, scheduledBalls:120, runs:60, wickets:2, legalBalls:60, target:121, gender:'female', competition:'wpl', targetRevised:false, interruption:false, superOver:false, status:'live', scoreRevision:'r1'};
console.log(JSON.stringify([
 predictChase(state,artifact),
 predictChase(state,artifact,{allowResearch:true}),
 ...[{format:'ODI'},{innings:1},{targetRevised:true},{targetRevised:undefined},{legalBalls:17.5},{wickets:10},{runs:121},{scoreRevision:undefined},{superOver:true}].map(x=>predictChase({...state,...x},artifact,{allowResearch:true}))
]));
"""
        result = subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,capture_output=True,text=True,check=True)
        values = json.loads(result.stdout)
        self.assertEqual(values[0]['reason'], 'model_not_released')
        self.assertEqual(values[1]['status'], 'available')
        self.assertEqual(values[1]['inputScoreRevision'], 'r1')
        self.assertGreater(values[1]['chasingWinProbability'], 0)
        self.assertLess(values[1]['chasingWinProbability'], 1)
        self.assertTrue(all(v['status']=='unavailable' for v in values[2:]))

class ModelGuardAndParityTests(unittest.TestCase):
    def test_duplicate_match_ids_cannot_enter_different_splits(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            model.split_matches([{'id':'same','date':'2022-01-01'}, {'id':'same','date':'2024-01-01'}])

    def test_each_match_has_equal_training_weight(self):
        rec, _ = model.extract_match(match_fixture(),'x','wpl')
        short = {**rec, 'id':'y', 'states':rec['states'][:2]}
        _, _, weights, meta = model.matrix([rec,short])
        for match_id in ['x','y']:
            self.assertAlmostEqual(sum(w for w,m in zip(weights,meta) if m['id']==match_id),1.0)

    def test_invalid_artifact_fails_closed_without_throwing(self):
        result = subprocess.run(['node','--input-type=module','-e',r"""
import {predictChase} from './live_model/inference.mjs';
const artifact={schemaVersion:1,release:{status:'research_only'},support:{genders:['male'],competitions:['bpl']},model:{featureNames:['runsNeeded'],coefficients:{length:2},means:[0],scales:[1],calibration:{intercept:0,slope:1}}};
const state={format:'T20',innings:2,scheduledBalls:120,runs:50,wickets:2,legalBalls:60,target:150,gender:'male',competition:'bpl',targetRevised:false,interruption:false,superOver:false,status:'live',scoreRevision:'v1'};
try {console.log(JSON.stringify(predictChase(state,artifact,{allowResearch:true})));} catch {console.log(JSON.stringify({status:'threw'}));}
"""],cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout),{'status':'unavailable','reason':'invalid_model'})

    def test_python_js_features_and_probability_match_exported_candidate(self):
        artifact_path=ROOT/'live_model/candidate.json'
        if not artifact_path.exists(): self.skipTest('Run the offline pipeline to create the candidate')
        artifact=json.loads(artifact_path.read_text())
        states=[{'runs':r,'wickets':w,'legalBalls':b,'target':t,'gender':g} for r,w,b,t,g in [(0,0,0,160,'male'),(83,4,72,150,'female'),(130,7,114,150,'male')]]
        script=r"""
import {featureValues,predictChase} from './live_model/inference.mjs';
import {readFileSync} from 'node:fs';
const artifact=JSON.parse(readFileSync('./live_model/candidate.json','utf8'));
// Shadow parity test only. Override cohort allowlist without changing weights.
artifact.support.competitions=['test'];
const states=JSON.parse(process.argv[1]);
console.log(JSON.stringify(states.map(state=>({features:featureValues(state),prediction:predictChase({...state,format:'T20',innings:2,scheduledBalls:120,competition:'test',targetRevised:false,interruption:false,superOver:false,status:'live',scoreRevision:'test'},artifact,{allowResearch:true})}))));
"""
        results=json.loads(subprocess.run(['node','--input-type=module','-e',script,json.dumps(states)],cwd=ROOT,capture_output=True,text=True,check=True).stdout)
        for state,result in zip(states,results):
            np.testing.assert_allclose(model.features(state),[result['features'][k] for k in model.FEATURES],rtol=1e-12)
            m=artifact['model']; norm=(np.array(model.features(state))-m['means'])/m['scales']
            logit=m['coefficients'][0]+np.array(m['coefficients'][1:]) @ norm
            expected=model.sigmoid(m['calibration']['intercept']+m['calibration']['slope']*logit)
            self.assertAlmostEqual(result['prediction']['chasingWinProbability'],expected,places=12)
            self.assertTrue(result['prediction']['researchOnly'])


if __name__ == '__main__': unittest.main()
