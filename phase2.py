"""Phase 2 empirical inputs and fixed-boundary chronological model selection.

Historical starters condition the forecasts; missing pre-tip evidence is never
converted into verified lineups. Baseline remains the production default.
"""
from collections import Counter,defaultdict
from datetime import date,datetime
from dataclasses import asdict
import hashlib,json,math,random
import first_basket_engine as eng
import simulation
import opening_data

CATEGORIES=('rim','two_jump','three','other')


def smooth(counts,prior,strength):
    total=sum(counts.values())
    return {k:(counts.get(k,0)+strength*p)/(total+strength) for k,p in prior.items()}


def build_inputs(history,lineups,target_day,sequences,config):
    import research_tools as rt
    inputs=simulation.build_inputs(history,lineups,target_day)
    inputs['first_shot_reference']={pid:inputs['opening_team'][t]*q for t,d in inputs['teams'].items() for pid,q in d['shot_share'].items()}
    prior,_=rt.audit(rt.history_window(history,target_day));groups=defaultdict(list)
    for r in prior:groups[r['game_id']].append(r)
    records=[];rejected=[];target=date.fromisoformat(target_day)
    for gid,rows in sorted(groups.items()):
        if gid not in sequences:continue
        if not opening_data.valid_for_history(sequences[gid],rows):rejected.append(gid);continue
        records.append((sequences[gid],2**(-(target-date.fromisoformat(rows[0]['date'])).days/90)))
    firstcat=defaultdict(Counter);firstplayer=defaultdict(Counter);usage=defaultdict(Counter);second=defaultdict(Counter)
    shots=defaultdict(lambda:[0.,0.]);allowed=defaultdict(lambda:[0.,0.]);pool={2:[0.,0.],3:[0.,0.]}
    ft=defaultdict(lambda:[0.,0.]);foulplayers=defaultdict(Counter);actions=defaultdict(Counter);defactions=defaultdict(Counter)
    rebounds=defaultdict(Counter);trips=defaultdict(Counter);tipteam=defaultdict(lambda:[0.,0.]);tipplayer=defaultdict(lambda:[0.,0.])
    for record,w in records:
        teams=set(record['starters'].values())
        if record['tip']:
            for team,pid in record['tip']['jumpers'].items():
                won=int(record['tip']['winner']==team)
                tipteam[team][0]+=w;tipteam[team][1]+=w*won;tipplayer[(team,pid)][0]+=w;tipplayer[(team,pid)][1]+=w*won
        for e in record['events']:
            team=e['team'];opp=next(t for t in teams if t!=team);pid=e.get('player');kind=e['kind']
            if kind=='shot':
                actions[team]['shot']+=w;defactions[opp]['shot']+=w;usage[team][pid]+=w
                if e['second_chance']:second[team][pid]+=w
                if e['first_team_shot']:firstcat[team][e['category']]+=w;firstplayer[(team,e['category'])][pid]+=w
                if e['value'] in (2,3):
                    for values in (shots[(team,pid,e['value'])],allowed[(opp,e['value'])],pool[e['value']]):values[0]+=w;values[1]+=w*e['made']
            elif kind=='ft':
                ft[(team,pid)][0]+=w;ft[(team,pid)][1]+=w*e['made']
                if e['trip_start']:
                    foulplayers[team][pid]+=w;actions[team]['foul']+=w;defactions[opp]['foul']+=w;trips[team][e['shots']]+=w
            elif kind=='turnover':actions[team]['turnover']+=w;defactions[opp]['turnover']+=w
            elif kind=='rebound':rebounds[team]['off' if e['offensive'] else 'def']+=w
    rows=[];tiprates={}
    for team,data in inputs['teams'].items():
        players=lineups[team];opp=next(t for t in lineups if t!=team)
        lineup_weights=eng.lineup_player_weights(prior,players,team,target_day)
        role_weights={r[0]['player_id']:r for r in eng.recent_role_player_weights(prior,players,team,target_day)}
        # Blend correlated predictors as a heuristic, not independent observations.
        select={r[0]['player_id']:(1-min(r[5]/20,1))*r[6]+min(r[5]/20,1)*role_weights[r[0]['player_id']][6] for r in lineup_weights}
        select=simulation._normalize(select)
        cats=smooth(firstcat[team],{k:.25 for k in CATEGORIES},20)
        catplayers={cat:smooth({pid:firstplayer[(team,cat)][pid] for pid in data['players']},select,10) for cat in CATEGORIES}
        opening={pid:sum(cats[cat]*catplayers[cat][pid] for cat in CATEGORIES) for pid in data['players']}
        later=smooth({pid:usage[team][pid] for pid in data['players']},opening,20)
        secondshares=smooth({pid:second[team][pid] for pid in data['players']},later,20)
        foulshare=smooth({pid:foulplayers[team][pid] for pid in data['players']},data['foul_share'],10)
        make={};three={};free={}
        for p in players:
            pid=p['player_id'];make[pid]={}
            n2,n3=shots[(team,pid,2)][0],shots[(team,pid,3)][0]
            three[pid]=(n3+2)/(n2+n3+5) # Missing shot mix: explicit 40% scenario prior.
            for value in (2,3):
                n,m=shots[(team,pid,value)];pn,pm=pool[value];pooled=(pm+5)/(pn+10)
                q=(m+20*pooled)/(n+20);dn,dm=allowed[(opp,value)];defq=(dm+30*pooled)/(dn+30)
                odds=(q/(1-q))*((defq/(1-defq))/(pooled/(1-pooled)))**.5
                make[pid][value]=max(.02,min(.98,odds/(1+odds)))
            n,m=ft[(team,pid)];free[pid]=(m+20*config.free_throw_rate)/(n+20)
            old=next(r for r in inputs['evidence'] if r['Player ID']==pid)
            rows.append({**old,'Opening FG selection within team %':100*opening[pid],
                         'Early 2PT weighted attempts':n2,'Early 3PT weighted attempts':n3,
                         '2PT make %':100*make[pid][2],'3PT make %':100*make[pid][3],
                         '3PT mix %':100*three[pid],'FT make %':100*free[pid],
                         'Similar-lineup starts':next(r[8] for r in lineup_weights if r[0]['player_id']==pid),
                         'Second-chance weighted attempts':second[team][pid]})
        priors={'turnover':config.turnover_rate,'foul':config.shooting_foul_rate,'shot':1-config.turnover_rate-config.shooting_foul_rate}
        own=smooth(actions[team],priors,30);defense=smooth(defactions[opp],priors,30)
        event={k:(own[k]+defense[k])/2 for k in priors}
        rb=rebounds[team];orb=(rb['off']+20*config.offensive_rebound_rate)/(sum(rb.values())+20)
        candidates=[(tipplayer[(team,pid)][0],pid) for pid in data['players'] if tipplayer[(team,pid)][0]>0]
        jumper=max(candidates)[1] if candidates else None
        tn,tw=tipplayer[(team,jumper)] if jumper else tipteam[team]
        tiprates[team]=(tw+10)/(tn+20)
        data.update(opening_category=cats,category_players=catplayers,opening_share=opening,later_share=later,second_share=secondshares,
                    foul_share=foulshare,make_by_type=make,three_share=three,ft_make=free,event_probs=event,
                    offensive_rebound=orb,trip_shots=smooth(trips[team],{1:0.,2:1.,3:0.},20),
                    empirical_events=sum(actions[team].values()),inferred_jumper=jumper,weighted_tip_samples=tn,
                    tip_source='explicit jump-ball possession' if tn else 'neutral 50/50 assumption',
                    substitution_policy='No pregame bench/substitution model; fixed ten-starter scope')
    a,b=list(inputs['teams']);ra,rb=tiprates[a],tiprates[b]
    p=ra*(1-rb)/(ra*(1-rb)+rb*(1-ra));inputs['opening_team']={a:p,b:1-p}
    inputs['evidence']=rows;inputs['sequence_games']=len(records);inputs['rejected_sequence_games']=rejected
    inputs['assumptions']=['Opening categories are observed shot tendencies, not named designed plays.',
        'Defensive adjustment is opponent-team/type aggregate, not individual defensive assignments.',
        'Unknown historical pre-tip lineups remain unverified.',
        'No supported pregame substitution inputs; ten starters stay on court.',
        'Shrinkage strengths, 40% missing 3PT mix and neutral conversion priors are fixed assumptions.']
    return inputs


def simulate(history,lineups,target_day,sequences=None,config=None,*,input_transform=None):
    cfg=(config or simulation.SimulationConfig()).validate();sequences=sequences or {}
    inputs=build_inputs(history,lineups,target_day,sequences,cfg)
    if input_transform is not None:inputs=input_transform(inputs)
    return _simulate_inputs(inputs,lineups,target_day,cfg)


def _simulate_inputs(inputs,lineups,target_day,cfg):
    """Internal kernel for already validated inputs; ablations reuse identical inputs."""
    identity={'date':target_day,'teams':{t:d['players'] for t,d in inputs['teams'].items()},'seed':cfg.seed,'model':'phase2'}
    seed=int.from_bytes(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).digest()[:8],'big');rng=random.Random(seed)
    teams=list(inputs['teams']);base=inputs['baseline'];wins=Counter();firstshots=Counter();opportunities=Counter();unresolved=0;no_fg=0
    events=Counter();trials=cfg.trials
    for _ in range(trials):
        team=simulation._draw(rng,inputs['opening_team']);winner=None;seen_fg=False;seen_opportunity=False;team_attempts=Counter();second=False
        for step in range(cfg.max_events):
            d=inputs['teams'][team];other=teams[1] if team==teams[0] else teams[0];kind=simulation._draw(rng,d['event_probs']);events[kind]+=1
            if kind=='turnover':team=other;second=False;continue
            if kind=='foul':
                pid=simulation._draw(rng,d['foul_share']);shots=simulation._draw(rng,d['trip_shots'])
                if not seen_opportunity:opportunities[pid]+=1;seen_opportunity=True
                for attempt in range(shots):
                    events['free_throw_attempts']+=1
                    if rng.random()<d['ft_make'][pid]:winner=pid;events['free_throw_scores']+=1;break
                if winner:break
            else:
                if second:
                    pid=simulation._draw(rng,d['second_share']);value=3 if rng.random()<d['three_share'][pid] else 2;events['second_chance_attempts']+=1
                elif not team_attempts[team]:
                    cat=simulation._draw(rng,d['opening_category']);pid=simulation._draw(rng,d['category_players'][cat])
                    value=3 if cat=='three' else 2 if cat in ('rim','two_jump') else 3 if rng.random()<d['three_share'][pid] else 2
                else:
                    pid=simulation._draw(rng,d['later_share']);value=3 if rng.random()<d['three_share'][pid] else 2
                if not seen_fg:firstshots[pid]+=1;seen_fg=True
                if not seen_opportunity:opportunities[pid]+=1;seen_opportunity=True
                team_attempts[team]+=1;events[str(value)+'pt_attempts']+=1
                if rng.random()<d['make_by_type'][pid][value]:winner=pid;events[str(value)+'pt_scores']+=1;break
            if rng.random()<d['offensive_rebound']:second=True;events['offensive_rebounds']+=1
            else:team=other;second=False;events['defensive_rebounds']+=1
        if winner:wins[winner]+=1
        else:unresolved+=1
        if not seen_fg:no_fg+=1
    active=all(d['games']>=cfg.min_team_games for d in inputs['teams'].values());alpha=cfg.hybrid_weight if active else 0
    mc={pid:(wins[pid]+unresolved*base[pid])/trials for pid in base}
    hybrid={pid:(1-alpha)*base[pid]+alpha*mc[pid] for pid in base}
    se={pid:alpha*math.sqrt(max(0,(wins[pid]+unresolved*base[pid]**2)/trials-mc[pid]**2)/trials) for pid in base}
    fg_total=sum(firstshots.values())
    return {'baseline':base,'simulation':mc,'hybrid':hybrid,'hybrid_mc_se':se,'wins':dict(wins),
            'first_shot':{pid:firstshots[pid]/fg_total if fg_total else 0 for pid in base},
            'first_opportunity':{pid:opportunities[pid]/trials for pid in base},'no_field_goal_fraction':no_fg/trials,
            'unresolved_trials':unresolved,'effective_hybrid_weight':alpha,'minimum_history_met':active,
            'transitions':dict(events),'config':asdict(cfg),'derived_seed':seed,'inputs':inputs}


def verified_historical_lineup(snapshot,rows,actual_start=None):
    """Only an archived, pre-tip provider confirmation can establish verification."""
    import dashboard_core as core
    try:
        if not actual_start or not snapshot or snapshot['game_id']!=rows[0]['game_id'] or snapshot['date']!=rows[0]['date']:return False
        start=datetime.fromisoformat(snapshot['start_time'].replace('Z','+00:00'));saved=datetime.fromisoformat(snapshot['saved_at'].replace('Z','+00:00'))
        actual=datetime.fromisoformat(actual_start.replace('Z','+00:00'))
        if start.tzinfo is None or actual.tzinfo is None or actual!=start or saved.tzinfo is None or saved>=start:return False
        evidence=snapshot['lineup_evidence'];teams={r['team'] for r in rows}
        if set(evidence)!=teams:return False
        entry=next(iter(evidence.values()))
        game={'gameId':rows[0]['game_id'],'_date':rows[0]['date'],'start_time':snapshot['start_time'],'gameStatus':1,
              'awayTeam':{'teamTricode':entry['away']},'homeTeam':{'teamTricode':entry['home']}}
        for team in teams:
            e=evidence[team]
            if e.get('method')!='NBA feed confirmed' or e.get('team')!=team:return False
            if not core.nba_confirmation_matches(e,game,[r for r in rows if r['team']==team],saved):return False
        return True
    except (KeyError,TypeError,ValueError,AttributeError):return False


def forecast_history(history,sequences,config,min_training=100,start=None,end=None,archive=None,progress=lambda text:None):
    import research_tools as rt
    valid,issues=rt.audit(history);byday=defaultdict(lambda:defaultdict(list));archive=archive or {}
    for r in valid:byday[r['date']][r['game_id']].append(r)
    prior=[];forecasts=[]
    for day in sorted(byday):
        if end and day>end:break
        train=rt.history_window(prior,day);ngames=len({r['game_id'] for r in train})
        if ngames>=min_training and (start is None or day>=start):
            progress('Phase 2: '+day)
            for gid,rows in sorted(byday[day].items()):
                lineups={t:[r for r in rows if r['team']==t] for t in sorted({r['team'] for r in rows})}
                report=simulate(train,lineups,day,sequences,config)
                frequency=simulation._normalize({r['player_id']:1+sum(int(x['first_scorer']) for x in train if x['player_id']==r['player_id'] and x['team']==r['team']) for r in rows})
                actual=next(r['player_id'] for r in rows if int(r['first_scorer']))
                fg=next((r['player_id'] for r in rows if int(r['first_game_shot'])),None)
                # The first-FG forecast is conditional on a field-goal attempt before first score.
                if rows[0].get('opening_score_path') not in ('opening_fg_made','opening_fg_missed'):fg=None
                forecasts.append({'Date':day,'Game':gid,'Winner':actual,'First shooter':fg,'Baseline':report['baseline'],'Monte Carlo':report['simulation'],
                    'Frequency':frequency,'Uniform':{pid:.1 for pid in report['baseline']},'First shot':report['first_shot'],'First shot reference':report['inputs']['first_shot_reference'],
                    'Verified lineup':verified_historical_lineup(archive.get(gid),rows,sequences[gid].get('start_time') if gid in sequences and opening_data.valid_for_history(sequences[gid],rows) else None),'Active':report['minimum_history_met'],
                    'Training games':ngames,'Sequence games':report['inputs']['sequence_games'],
                    'Last training date':report['inputs']['last_training_date'],'Training fingerprint':report['inputs']['history_fingerprint'],
                    'Unresolved trials':report['unresolved_trials']})
        prior.extend(r for rows in byday[day].values() for r in rows)
    return forecasts,issues


def blended(row,weight,temperature):
    import research_tools as rt
    w=weight if row['Active'] else 0
    probs={pid:(1-w)*p+w*row['Monte Carlo'][pid] for pid,p in row['Baseline'].items()}
    return rt.temper_probabilities(probs,temperature)


def metrics(forecasts,label,weight=0,temperature=1):
    import research_tools as rt
    rows=[];calibration=[]
    for row in forecasts:
        probs=blended(row,weight,temperature) if label=='Selected hybrid' else row[label]
        win=row['Winner'];p=probs[win]
        rows.append({'Date':row['Date'],'Game':row['Game'],'Top-1 credit':rt.top_k_credit(probs,win,1),'Top-3 credit':rt.top_k_credit(probs,win,3),
                     'Log loss':-math.log(p) if p else math.inf,'Brier':sum((q-int(pid==win))**2 for pid,q in probs.items())})
        calibration.extend((q,int(pid==win)) for pid,q in probs.items())
    bins=[];ece=0
    for lo,hi in ((0,.05),(.05,.1),(.1,.15),(.15,.2),(.2,.3),(.3,1.000001)):
        data=[(q,y) for q,y in calibration if lo<=q<hi]
        if not data:continue
        pred=sum(q for q,y in data)/len(data);obs=sum(y for q,y in data)/len(data)
        ece+=len(data)*abs(pred-obs)/max(1,len(calibration))
        bins.append({'Band':f'{lo:.2f}-{min(hi,1):.2f}','Player forecasts':len(data),'Predicted %':pred*100,'Observed %':obs*100})
    return {'metrics':{**rt.evaluation_metrics(rows),'Calibration ECE pp':100*ece if rows else None},'games':rows,'calibration':bins}


def select(validation,weights=(0,.15,.35,.5),temperatures=(.8,1,1.25)):
    dates=len({r['Date'] for r in validation});calibrated=len(validation)>=100 and dates>=20
    if len(validation)<50 or dates<10:weights=(0,);temperatures=(1,)
    elif not calibrated:temperatures=(1,)
    candidates=[]
    for weight in weights:
        for temperature in temperatures:
            result=metrics(validation,'Selected hybrid',weight,temperature)['metrics']
            candidates.append({'Weight':weight,'Temperature':temperature,**result})
    scored=[r for r in candidates if r['Log loss'] is not None]
    best=min(scored,key=lambda r:(r['Log loss'],r['Weight'],abs(r['Temperature']-1))) if scored else {'Weight':0,'Temperature':1}
    return {'weight':best['Weight'],'temperature':best['Temperature'],'validation_games':len(validation),'validation_dates':dates,
            'calibration_sample_minimum_met':calibrated,'candidates':candidates,'selection_metric':'validation log loss'}


def evaluate_holdout(history,sequences,test_start,test_end,config=None,min_training=100,archive=None,progress=lambda text:None,on_lock=None):
    import research_tools as rt
    cfg=(config or simulation.SimulationConfig(trials=2000)).validate()
    if type(min_training) is not int or min_training<1:raise ValueError('Invalid training minimum.')
    if date.fromisoformat(test_start)>date.fromisoformat(test_end):raise ValueError('Test dates are reversed.')
    training=[r for r in history if r['date']<test_start]
    validation,excluded=forecast_history(training,sequences,cfg,min_training,archive=archive,progress=progress)
    selection=select(validation)
    selection.update(test_start=test_start,test_end=test_end,config=asdict(cfg),training_fingerprint=rt.fingerprint(training))
    if on_lock:on_lock(selection) # Persist chosen settings before accessing test outcomes.
    test,test_excluded=forecast_history(history,sequences,cfg,min_training,start=test_start,end=test_end,archive=archive,progress=progress)
    summary=[];calibration=[];comparisons=[];details=[]
    labels=('Baseline','Monte Carlo','Selected hybrid','Frequency','Uniform')
    for cohort,subset in (('All test games',test),('Verified historical lineups',[r for r in test if r['Verified lineup']]),('Unverified historical lineups',[r for r in test if not r['Verified lineup']])):
        results={label:metrics(subset,label,selection['weight'],selection['temperature']) for label in labels}
        for label,result in results.items():
            summary.append({'Cohort':cohort,'Model':label,'Dates':len({r['Date'] for r in subset}),**result['metrics']})
            calibration.extend({'Cohort':cohort,'Model':label,**r} for r in result['calibration'])
        for label in labels[1:]:
            finite=all(math.isfinite(r['Log loss']) for name in ('Baseline',label) for r in results[name]['games'])
            paired=rt.compare_evaluations(results['Baseline'],results[label],metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if finite else ('Brier','Top-1 credit','Top-3 credit'))
            comparisons.extend({'Cohort':cohort,'Model':label,'Games':paired['games'],'Dates':paired['dates'],**r} for r in paired['metrics'])
            if not finite:comparisons.append({'Cohort':cohort,'Model':label,'Metric':'Log loss','Note':'Non-finite loss retained; interval withheld.'})
        if cohort=='All test games':
            for label,result in results.items():details.extend({'Model':label,**r} for r in result['games'])
    first=[r for r in test if r['First shooter'] and sum(r['First shot'].values())>0]
    first_hit=sum(rt.top_k_credit(r['First shot'],r['First shooter'],1) for r in first)
    return {'selection':selection,'summary':summary,'calibration':calibration,'comparisons':comparisons,'details':details,
            'diagnostics':[{k:v for k,v in r.items() if k not in labels and k not in ('First shot','First shot reference')} for r in test],
            'first_shot':{'Eligible games':len(first),'Top-1 hit %':100*first_hit/len(first) if first else None,
                          'Recent-shot proxy Top-1 hit %':100*sum(rt.top_k_credit(r['First shot reference'],r['First shooter'],1) for r in first)/len(first) if first else None,
                          'Uniform Top-1 hit %':10 if first else None},
            'fingerprint':rt.fingerprint(history),'sequence_fingerprint':rt.fingerprint(sequences),'evaluated_games':len(test),
            'excluded_training_games':len(excluded),'excluded_total_games':len(test_excluded)}
