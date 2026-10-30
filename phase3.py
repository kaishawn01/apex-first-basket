"""Phase 3 research: selector ablations, complete outcome support, no promotion."""
import copy,math,json
from collections import defaultdict,Counter
from datetime import date
import first_basket_engine as eng
import simulation,phase2,opening_data,research_tools as rt
OTHER='OTHER'
SELECTORS=('simple','role','empirical','hybrid','phase2','neutral_tip','opponent')


def temper(probabilities,temperature=1):
    """Temperature scaling for the ten players PLUS Other; legacy helper stays unchanged."""
    if isinstance(temperature,bool) or not isinstance(temperature,(int,float)) or not math.isfinite(temperature) or not .5<=temperature<=2:raise ValueError('Invalid temperature')
    if len(probabilities)!=11 or OTHER not in probabilities or any(not math.isfinite(p) or p<=0 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-8:raise ValueError('Expected eleven positive normalized outcomes')
    if temperature==1:return dict(probabilities)
    logits={pid:math.log(p)/temperature for pid,p in probabilities.items()};peak=max(logits.values())
    return simulation._normalize({pid:math.exp(x-peak) for pid,x in logits.items()})

def selector(history,lineups,day,inputs,method='simple',half_life=90,*,_cache=None):
    if method not in SELECTORS or half_life not in (30,90,180):raise ValueError('Unsupported selector setting')
    history=rt.history_window(history,day);out={};counts={}
    cache={} if _cache is None else _cache
    for team,players in lineups.items():
        opp=next(t for t in lineups if t!=team)
        key=(team,half_life)
        if key not in cache:
            base=eng.recent_player_weights(history,players,team,day,half_life=half_life)
            simple=simulation._normalize({r[0]['player_id']:r[6] for r in base})
            role=simulation._normalize({r[0]['player_id']:r[6] for r in eng.recent_role_player_weights(history,players,team,day,half_life=half_life)})
            ids=set(simple);weighted=Counter();matched=Counter();n=0
            for r in history:
                if r['team']!=team or r['player_id'] not in ids:continue
                w=2**(-(date.fromisoformat(day)-date.fromisoformat(r['date'])).days/half_life)
                if int(r['first_team_shot']):weighted[r['player_id']]+=w;n+=1
                if r['opponent']==opp and int(r['first_team_shot']):matched[r['player_id']]+=w
            cache[key]=(simple,role,ids,weighted,matched,n)
        simple,role,ids,weighted,matched,n=cache[key]
        empirical=phase2.smooth(weighted,simple,20)
        chosen={'simple':simple,'neutral_tip':simple,'role':role,'empirical':empirical,'hybrid':{pid:.5*simple[pid]+.5*role[pid] for pid in ids},'phase2':inputs['teams'][team]['opening_share'],'opponent':phase2.smooth(matched,simple,30)}[method]
        teamprob=.5 if method=='neutral_tip' else sum(inputs['first_shot_reference'][pid] for pid in ids)
        if method=='phase2':teamprob=inputs['opening_team'][team]
        out.update({pid:teamprob*q for pid,q in chosen.items()});counts[team]={'first_team_attempts':n,'opponent_weighted_attempts':sum(matched.values())}
    return simulation._normalize(out),counts

def other_prior(records,day,lineups):
    prior=[r for r in records.values() if r['date']<day and 0<(date.fromisoformat(day)-date.fromisoformat(r['date'])).days<=400 and r['status']=='resolved' and r.get('rows')]
    # A complete outcome outside the recorded ten belongs to OTHER, never to a starter.
    n=len(prior);k=sum(r['scorer_id'] not in {x['player_id'] for x in r['rows']} for r in prior)
    # Fixed Beta(.5,49.5) prior = 1%; assumption rather than a league estimate.
    a,b=k+.5,n-k+49.5;p=a/(a+b);sd=math.sqrt(a*b/((a+b)**2*(a+b+1)))
    return p,{'games':n,'other_outcomes':k,'assumed_prior_mean':.01,'posterior_sd':sd,'interval_note':'SD reflects beta-binomial sampling, not missing-data uncertainty'}

def with_other(probs,mass):
    if not 0<=mass<1 or not probs or any(not math.isfinite(v) or v<0 for v in probs.values()) or abs(sum(probs.values())-1)>1e-8:raise ValueError('Invalid probability distribution')
    return {**{pid:(1-mass)*p for pid,p in probs.items()},OTHER:mass}

def apply_selection(inputs,probs):
    for team,data in inputs['teams'].items():
        mass=sum(probs[pid] for pid in data['players']);inputs['opening_team'][team]=mass
        share={pid:probs[pid]/mass for pid in data['players']}
        # Remove category-dependent shooter selection; retain learned shot types and conversion.
        data['category_players']={cat:share for cat in data['opening_category']};data['opening_share']=share
    return inputs

def forecast(history,lineups,day,sequences,records,config,method='simple',half_life=90,*,input_transform=None):
    chosen={}
    def transform(inputs):
        probs,counts=selector(history,lineups,day,inputs,method,half_life);chosen.update(probs=probs,counts=counts)
        apply_selection(inputs,probs)
        return input_transform(inputs) if input_transform is not None else inputs
    report=phase2.simulate(history,lineups,day,sequences,config,input_transform=transform)
    report['inputs']['assumptions'].append('Simple selector removes category-conditioned shooter assignment; first attempts retain team shot-category mix, while player-specific mix applies to later and second-chance attempts.')
    mass,evidence=other_prior(records,day,lineups)
    report['complete']={label:with_other(report[key],mass) for label,key in [('Baseline + Other','baseline'),('Monte Carlo','simulation'),('Hybrid','hybrid')]}
    report['complete']['Simple proxy']=with_other(chosen['probs'],mass)
    report.update(other_mass=mass,other_evidence=evidence,selector=method,selector_half_life=half_life,first_shot_proxy=chosen['probs'],selection_evidence=chosen['counts'])
    return report

def forecasts(history,sequences,records,config,start=None,end=None,min_training=100,method='simple',half_life=90,progress=lambda text:None,archive=None):
    rows=[];excluded=[]
    for gid,r in sorted(records.items(),key=lambda item:(item[1]['date'],item[0])):
        day=r['date']
        if (start and day<start) or (end and day>end):continue
        if r['status']!='resolved' or not r.get('rows'):
            excluded.append({'game':gid,'reason':'Unresolved outcome or unavailable ten-player modeling lineup','warnings':r['warnings']});continue
        train=rt.history_window(history,day)
        if len({x['game_id'] for x in train})<min_training:continue
        lineups={t:[x for x in r['rows'] if x['team']==t] for t in sorted({x['team'] for x in r['rows']})}
        progress('Phase 3 '+day+' '+gid)
        report=forecast(train,lineups,day,sequences,records,config,method,half_life)
        old=phase2.simulate(train,lineups,day,sequences,config)
        actual=r['scorer_id'] if r['scorer_id'] in report['baseline'] else OTHER
        first=next((x['player_id'] for x in r['rows'] if int(x['first_game_shot'])),None)
        if r['rows'][0].get('opening_score_path') not in ('opening_fg_made','opening_fg_missed'):first=None
        ablations={};selector_cache={}
        for mode in SELECTORS:
            for half in (30,90,180):
                ablations[f'{mode}:{half}']=selector(train,lineups,day,old['inputs'],mode,half,_cache=selector_cache)[0]
        legacy={**report['baseline'],OTHER:0.}
        rows.append({'Date':day,'Game':gid,'Winner':actual,'First shooter':first,'Starter status':r['starter_status'],'Legacy Baseline':legacy,**report['complete'],
            'Phase 2 hybrid':with_other(old['hybrid'],report['other_mass']),'Uniform':{pid:1/11 for pid in legacy},'Phase 2 first shot':old['first_shot'],
            'Ablations':ablations,'First shot':report['first_shot'],'Active':report['minimum_history_met'],
            'Verified lineup':phase2.verified_historical_lineup((archive or {}).get(gid),r['rows'],r.get('start_time')),
            'Training games':len({x['game_id'] for x in train}),'Last training date':max(x['date'] for x in train),'Other evidence':report['other_evidence'],
            'Target lineups':{t:[x['player_id'] for x in ps] for t,ps in lineups.items()},'Player teams':{x['player_id']:x['team'] for x in r['rows']}})
    return rows,excluded

def shot_metrics(rows,key):
    selected=[r for r in rows if r['First shooter'] and r['First shooter'] in (r['Ablations'].get(key,{}) if ':' in key else r.get(key,{}))]
    def probs(r):return r['Ablations'][key] if ':' in key else r[key]
    return {'games':len(selected),'top1':sum(rt.top_k_credit(probs(r),r['First shooter'],1) for r in selected)/len(selected) if selected else None,'log_loss':sum(-math.log(max(probs(r)[r['First shooter']],1e-15)) for r in selected)/len(selected) if selected else None}

def ablation_report(rows):
    dates=sorted({r['Date'] for r in rows});cut=dates[len(dates)//2] if dates else ''
    cohorts={'all':rows,'early':[r for r in rows if r['Date']<cut],'late':[r for r in rows if r['Date']>=cut]}
    return [{'selector':key,**{name:shot_metrics(rs,key) for name,rs in cohorts.items()}} for key in [f'{s}:{h}' for s in SELECTORS for h in (30,90,180)]+['Phase 2 first shot','First shot']]

def select(rows):
    # Promotion requires independently positive accuracy and log loss in BOTH validation halves.
    ablations=ablation_report(rows);base=next(x for x in ablations if x['selector']=='simple:90')
    eligible=[x for x in ablations if ':' in x['selector'] and all(x[c]['games']>=50 and x[c]['top1']>base[c]['top1'] and x[c]['log_loss']<base[c]['log_loss'] for c in ('early','late'))]
    chosen=min(eligible,key=lambda x:x['all']['log_loss'])['selector'] if eligible else 'simple:90'
    # This experiment simulates the simple selector throughout. Any analytic challenger needs a fresh simulation study.
    candidates=[]
    for w in ((0,.15,.35,.5) if len(rows)>=50 and len({r['Date'] for r in rows})>=10 else (0,)):
        for temp in ((.8,1,1.25) if len(rows)>=100 and len({r['Date'] for r in rows})>=20 else (1,)):
            loss=[]
            for r in rows:
                p=temper({pid:(1-(w if r['Active'] else 0))*q+(w if r['Active'] else 0)*r['Monte Carlo'][pid] for pid,q in r['Baseline + Other'].items()},temp)
                loss.append(-math.log(p[r['Winner']]))
            candidates.append({'weight':w,'temperature':temp,'log_loss':sum(loss)/len(loss) if loss else None})
    best=min(candidates,key=lambda x:(x['log_loss'] if x['log_loss'] is not None else math.inf,x['weight'],abs(x['temperature']-1)))
    return {'selector':'simple','half_life':90,'analytic_candidate':chosen,'selector_promotion':False,'validation_games':len(rows),'candidates':candidates,**best}

def summarize(rows,selection):
    labels=('Legacy Baseline','Baseline + Other','Simple proxy','Monte Carlo','Phase 2 hybrid','Selected hybrid','Calibrated baseline','Uniform','Uniform + Other')
    copied=copy.deepcopy(rows)
    for r in copied:
        w=selection['weight'] if r['Active'] else 0
        r['Uniform + Other']=with_other({pid:.1 for pid in r['Legacy Baseline'] if pid!=OTHER},r['Baseline + Other'][OTHER])
        r['Selected hybrid']=temper({pid:(1-w)*p+w*r['Monte Carlo'][pid] for pid,p in r['Baseline + Other'].items()},selection['temperature'])
        r['Calibrated baseline']=temper(r['Baseline + Other'],selection['baseline_temperature'])
    summary=[];comparisons=[];calibration=[]
    for cohort,subset in [('All resolved modeled games',copied),('Starter outcomes',[r for r in copied if r['Winner']!=OTHER]),('Other outcomes',[r for r in copied if r['Winner']==OTHER]),('Verified pre-tip lineups',[r for r in copied if r.get('Verified lineup')]),('Unverified pre-tip lineups',[r for r in copied if not r.get('Verified lineup')])]:
        results={label:phase2.metrics([{**r,'Prediction':r[label]} for r in subset],'Prediction') for label in labels}
        for label,result in results.items():
            summary.append({'cohort':cohort,'model':label,**result['metrics']})
            calibration.extend({'cohort':cohort,'model':label,**b} for b in result['calibration'])
        for label in ('Selected hybrid','Calibrated baseline','Monte Carlo'):
            cmp=rt.compare_evaluations(results['Baseline + Other'],results[label])
            comparisons.append({'cohort':cohort,'model':label,**cmp})
    return {'summary':summary,'comparisons':comparisons,'calibration':calibration,'first_shot':ablation_report(copied),'games':len(copied),'verified_pretip_games':sum(bool(r.get('Verified lineup')) for r in copied),'note':'No provider-verified pre-tip evidence in public sample; observed starters condition models. OTHER is an aggregate category; 11-way Uniform differs from Phase 2 ten-player Uniform.'}

def lock_selection(validation):
    chosen=select(validation)
    baseline=[c for c in chosen['candidates'] if c['weight']==0]
    chosen['baseline_temperature']=min(baseline,key=lambda x:(x['log_loss'] if x['log_loss'] is not None else math.inf,abs(x['temperature']-1)))['temperature']
    return chosen

def diagnose(rows,history):
    """Descriptive miss patterns, never model selection on held-out groups."""
    groups=defaultdict(list);pairs=Counter()
    for r in rows:
        actual=r['First shooter']
        if not actual:continue
        simple=r['Ablations']['simple:90'];complex_=r['Phase 2 first shot']
        team=r['Player teams'][actual];prior=rt.history_window(history,r['Date'])
        starts=sum(x['team']==team and x['player_id']==actual for x in prior)
        rate=sum(x['team']==team and x['player_id']==actual and int(x['first_team_shot']) for x in prior)/max(1,starts)
        role='frequent opening shooter (>=20%)' if rate>=.2 else 'less frequent opening shooter (<20%)'
        sample='under 10 prior starts' if starts<10 else '10+ prior starts'
        target=set(r['Target lineups'][team]);games=defaultdict(set)
        for x in prior:
            if x['team']==team:games[x['game_id']].add(x['player_id'])
        exact=sum(ids==target for ids in games.values());lineup='under 5 exact-lineup games' if exact<5 else '5+ exact-lineup games'
        for group in ('team:'+team,'role:'+role,'sample:'+sample,'lineup:'+lineup):groups[group].append(r)
        oldtop=max(complex_,key=complex_.get);newtop=max(simple,key=simple.get)
        if oldtop!=newtop:pairs[(oldtop,newtop,actual)]+=1
    return {'groups':[{'group':g,'simple':shot_metrics(rs,'simple:90'),'phase2':shot_metrics(rs,'Phase 2 first shot')} for g,rs in sorted(groups.items())],
            'most_common_disagreements':[{'phase2_top':a,'simple_top':b,'actual':c,'games':n} for (a,b,c),n in pairs.most_common(15)],
            'limitations':'Descriptive subgroups have small samples and multiple comparisons. Role bins use prior opening frequency, not player position. Exact-lineup samples are observational, not pre-tip confirmation.'}

def opening_exposure(sequence):
    """Descriptive outcome strata only, never a pregame predictor from the target game."""
    if not sequence:return 'Unavailable opening sequence'
    changed=False
    for event in sequence.get('events',[]):
        if event['kind']=='turnover' or (event['kind']=='rebound' and not event['offensive']):changed=True
        elif event['kind']=='ft' and event['made']:return 'Free throw before first FG'
        elif event['kind']=='shot':return 'First FG after a possession change' if changed else 'First FG on opening possession (event proxy)'
    return 'No observed FG before sequence cutoff'
