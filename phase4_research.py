"""Exploratory ablations of known January data; never selects final-test settings."""
import math,copy
from collections import defaultdict
from datetime import date
import phase3,phase2,simulation,opening_data,research_tools as rt
VARIANTS=('reference','neutral_tip','role_selector','neutral_conversion','uniform_foul_shooter','neutral_foul_frequency','neutral_ft_accuracy','no_turnovers','no_offensive_rebounds','no_opponent_conversion','strong_conversion_shrinkage','weak_conversion_shrinkage','selection_decay_30','selection_decay_180','seed_3001','seed_3002')

def own_conversion(history,sequences,day,strength=20):
    prior=rt.history_window(history,day);groups=defaultdict(list)
    for r in prior:groups[r['game_id']].append(r)
    shots=defaultdict(lambda:[0.,0.]);pool={2:[0.,0.],3:[0.,0.]}
    for gid,rows in groups.items():
        record=sequences.get(gid)
        if not record or not opening_data.valid_for_history(record,rows):continue
        w=2**(-(date.fromisoformat(day)-date.fromisoformat(rows[0]['date'])).days/90)
        for e in record['events']:
            if e['kind']=='shot' and e['value'] in (2,3):
                for counter in (shots[(e['team'],e['player'],e['value'])],pool[e['value']]):counter[0]+=w;counter[1]+=w*e['made']
    def apply(inputs):
        for team,data in inputs['teams'].items():
            for pid in data['players']:
                for value in (2,3):
                    n,m=shots[(team,pid,value)];pn,pm=pool[value]
                    data['make_by_type'][pid][value]=(m+strength*(pm+5)/(pn+10))/(n+strength)
        return inputs
    return apply

def transform(variant,history,sequences,day):
    if variant in ('no_opponent_conversion','strong_conversion_shrinkage','weak_conversion_shrinkage'):
        return own_conversion(history,sequences,day,100 if variant.startswith('strong') else 5 if variant.startswith('weak') else 20)
    def apply(inputs):
        if variant=='neutral_tip':inputs['opening_team']={t:.5 for t in inputs['teams']}
        for t,d in inputs['teams'].items():
            if variant=='neutral_conversion':d['make_by_type']={pid:{2:.5,3:.35} for pid in d['players']}
            if variant=='uniform_foul_shooter':d['foul_share']={pid:.2 for pid in d['players']}
            if variant=='neutral_ft_accuracy':d['ft_make']={pid:.77 for pid in d['players']}
            if variant=='neutral_foul_frequency':
                total=d['event_probs']['shot']+d['event_probs']['turnover']
                d['event_probs']={'foul':.1,'shot':.9*d['event_probs']['shot']/total,'turnover':.9*d['event_probs']['turnover']/total}
            if variant=='no_turnovers':d['event_probs']=simulation._normalize({**d['event_probs'],'turnover':0.})
            if variant=='no_offensive_rebounds':d['offensive_rebound']=0.
        return inputs
    return apply

def ablate(history,sequences,records,start,end,progress=lambda s:None,trials=2000):
    rows=[]
    for gid,r in sorted(records.items(),key=lambda x:(x[1]['date'],x[0])):
        if not start<=r['date']<=end or r['status']!='resolved' or not r['rows']:continue
        day=r['date'];train=rt.history_window(history,day);lineups={t:[x for x in r['rows'] if x['team']==t] for t in sorted({x['team'] for x in r['rows']})}
        if len({x['game_id'] for x in train})<100:continue
        item={'Game':gid,'Date':day,'Winner':r['scorer_id'] if r['scorer_id'] in {x['player_id'] for x in r['rows']} else 'OTHER'}
        inputs=phase2.build_inputs(train,lineups,day,sequences,simulation.SimulationConfig(trials=trials,seed=3000))
        mass,_=phase3.other_prior(records,day,lineups);selected={}
        for variant in VARIANTS:
            seed=int(variant[5:]) if variant.startswith('seed_') else 3000
            method='role' if variant=='role_selector' else 'simple';half=30 if variant=='selection_decay_30' else 180 if variant=='selection_decay_180' else 90
            if (method,half) not in selected:selected[(method,half)]=phase3.selector(train,lineups,day,inputs,method,half)[0]
            prepared=copy.deepcopy(inputs);phase3.apply_selection(prepared,selected[(method,half)])
            transform(variant,train,sequences,day)(prepared)
            report=phase2._simulate_inputs(prepared,lineups,day,simulation.SimulationConfig(trials=trials,seed=seed))
            item[variant]=phase3.with_other(report['simulation'],mass)
        rows.append(item);progress(f'January diagnostic {len(rows)}: {gid}')
    metrics={v:phase2.metrics(rows,v) for v in VARIANTS}
    comparisons=[]
    for v in VARIANTS[1:]:
        finite=all(math.isfinite(x['Log loss']) for label in ('reference',v) for x in metrics[label]['games'])
        comparisons.append({'variant':v,**rt.compare_evaluations(metrics['reference'],metrics[v],metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if finite else ('Brier','Top-1 credit','Top-3 credit'))})
    return {'sample':'Known January 1–21, 2026: exploratory only','games':len(rows),'summary':[{'variant':v,**m['metrics']} for v,m in metrics.items()],'comparisons':comparisons,'notes':['No settings selected from this report. Multiple exploratory comparisons; no multiplicity correction.','Zeroing turnovers/rebounds is a counterfactual diagnostic, not a proposed NBA model.','Conversion shrinkage variants remove opponent conversion too; compare them to no_opponent_conversion.','Selection decay changes only first-shot selection, not all simulator recency weights.','Seeds are sensitivity checks, never a best-seed search.']}
