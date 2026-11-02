"""V3 research simulator: explicit assumptions, deterministic seeds, no network calls.

Historical records contain starter opening attempts and first scores, not full
possessions. Turnover/foul/rebound/free-throw rates below are scenario assumptions.
"""
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math
import random
from collections import defaultdict
import first_basket_engine as eng


@dataclass(frozen=True)
class SimulationConfig:
    trials: int = 5000
    seed: int = 3000
    max_events: int = 60
    hybrid_weight: float = .35
    turnover_rate: float = .13
    shooting_foul_rate: float = .10
    offensive_rebound_rate: float = .24
    free_throw_rate: float = .77
    min_team_games: int = 10

    def validate(self):
        for name,lo,hi in (('trials',100,100000),('seed',0,2**32-1),('max_events',1,200),('min_team_games',0,400)):
            value=getattr(self,name)
            if type(value) is not int or not lo<=value<=hi:raise ValueError(f'Invalid simulation {name}.')
        for name in ('hybrid_weight','turnover_rate','shooting_foul_rate','offensive_rebound_rate','free_throw_rate'):
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
                raise ValueError(f'Invalid simulation {name}.')
        if self.turnover_rate+self.shooting_foul_rate>1:raise ValueError('Turnover and foul probabilities exceed one.')
        return self


def _normalize(values):
    total=sum(values.values())
    if total<=0 or any(not math.isfinite(v) or v<0 for v in values.values()):raise ValueError('Invalid simulation weights.')
    return {pid:v/total for pid,v in sorted(values.items())}


def build_inputs(history,lineups,target_day):
    # Import here to keep the legacy engine/research modules independent at import time.
    from research_tools import audit, history_window, fingerprint
    if len(lineups)!=2 or any(t not in eng.TEAMS for t in lineups):raise ValueError('Two valid NBA teams are required.')
    if any(len(players)!=5 for players in lineups.values()):raise ValueError('Five starters per team are required.')
    ids=[p['player_id'] for players in lineups.values() for p in players]
    if len(set(ids))!=10:raise ValueError('Ten distinct player IDs are required.')
    target=date.fromisoformat(target_day)
    prior,issues=audit(history_window(history,target_day))
    if issues:raise ValueError('Repair invalid earlier history before simulation.')
    prior=sorted(prior,key=lambda r:(r['date'],r['game_id'],r['team'],r['player_id']))
    ordered={t:sorted(players,key=lambda p:p['player_id']) for t,players in sorted(lineups.items())}
    baseline=eng.predict_first_score(prior,ordered,target_day,'baseline')
    games=defaultdict(list)
    for row in prior:games[row['game_id']].append(row)
    team_inputs={};evidence=[]
    for team,players in ordered.items():
        team_games=[rows for rows in games.values() if any(r['team']==team for r in rows)]
        mass=0.0;first=0.0;observed=0
        for rows in team_games:
            opening={r['team'] for r in rows if int(r['tip_first_action'])}
            if len(opening)!=1:continue
            w=2**(-(target-date.fromisoformat(rows[0]['date'])).days/90)
            mass+=w;first+=w*(team in opening);observed+=1
        opening_rate=(first+10)/(mass+20)
        weights=eng.conversion_player_weights(prior,players,team,target_day)
        shot_share=_normalize({r[0]['player_id']:r[6] for r in weights})
        foul_share=_normalize({r[0]['player_id']:r[7] for r in weights})
        make={r[0]['player_id']:r[8] for r in weights}
        known_total=0
        for row in weights:
            player=row[0];pid=player['player_id']
            records=[r for r in prior if r['team']==team and r['player_id']==pid]
            known=sum(int(r['first_team_shot']) and str(r.get('first_team_shot_made','')) in ('0','1') for r in records)
            known_total+=known
            evidence.append({'Player':player['player'],'Team':team,'Player ID':pid,'Recorded starts':len(records),
                             'Known opening outcomes':known,'Weighted known outcomes':row[9],
                             'Shot selection %':100*shot_share[pid],'Smoothed make %':100*make[pid],
                             'Foul-shooter proxy %':100*foul_share[pid]})
        team_inputs[team]={'players':[p['player_id'] for p in players],'shot_share':shot_share,'foul_share':foul_share,
                          'make':make,'games':len(team_games),'opening_proxy_games':observed,
                          'opening_rate':opening_rate,'known_opening_outcomes':known_total}
    a,b=list(ordered);ra=team_inputs[a]['opening_rate'];rb=team_inputs[b]['opening_rate']
    opening_a=max(.25,min(.75,ra*(1-rb)/(ra*(1-rb)+rb*(1-ra))))
    return {'teams':team_inputs,'baseline':baseline,'opening_team':{a:opening_a,b:1-opening_a},
            'evidence':evidence,'target_day':target_day,'history_fingerprint':fingerprint(prior),
            'training_games':len(games),'last_training_date':max((r['date'] for r in prior),default=None)}


def _draw(rng,probabilities):
    mark=rng.random();cumulative=0
    for key,p in probabilities.items():
        cumulative+=p
        if mark<cumulative:return key
    return next(reversed(probabilities))


def simulate(history,lineups,target_day,config=None):
    config=(config or SimulationConfig()).validate()
    inputs=build_inputs(history,lineups,target_day)
    # Game order, roster display order and process hash randomization cannot change draws.
    identity={'date':target_day,'teams':{t:d['players'] for t,d in inputs['teams'].items()},'seed':config.seed}
    seed=int.from_bytes(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).digest()[:8],'big')
    rng=random.Random(seed);teams=list(inputs['teams']);base=inputs['baseline']
    wins={pid:0 for pid in sorted(base)};unresolved=0;events=0
    transitions={'turnovers':0,'foul_trips':0,'field_goal_attempts':0,'offensive_rebounds':0,'defensive_rebounds':0,'free_throw_scores':0,'field_goal_scores':0}
    for _ in range(config.trials):
        team=_draw(rng,inputs['opening_team']);winner=None
        for step in range(config.max_events):
            events+=1;data=inputs['teams'][team];other=teams[1] if team==teams[0] else teams[0]
            action=rng.random()
            if action<config.turnover_rate:
                transitions['turnovers']+=1;team=other;continue
            if action<config.turnover_rate+config.shooting_foul_rate:
                transitions['foul_trips']+=1
                pid=_draw(rng,data['foul_share'])
                # First made free throw ends the trial; two-shot foul approximation.
                if rng.random()<config.free_throw_rate or rng.random()<config.free_throw_rate:
                    winner=pid;transitions['free_throw_scores']+=1;break
            else:
                transitions['field_goal_attempts']+=1;pid=_draw(rng,data['shot_share'])
                if rng.random()<data['make'][pid]:
                    winner=pid;transitions['field_goal_scores']+=1;break
            if rng.random()<config.offensive_rebound_rate:
                transitions['offensive_rebounds']+=1
            else:
                transitions['defensive_rebounds']+=1;team=other
        if winner is None:unresolved+=1
        else:wins[winner]+=1
    active=all(d['games']>=config.min_team_games for d in inputs['teams'].values())
    alpha=config.hybrid_weight if active else 0.0
    n=config.trials
    # Do not drop or fabricate a scorer for capped trials. Allocate their mass to
    # the existing forecast, explicitly report it, and retain raw simulated counts.
    simulation={pid:(wins[pid]+unresolved*base[pid])/n for pid in base}
    hybrid={pid:(1-alpha)*base[pid]+alpha*simulation[pid] for pid in base}
    se={pid:alpha*math.sqrt(max(0,(wins[pid]+unresolved*base[pid]**2)/n-simulation[pid]**2)/n) for pid in base}
    return {'baseline':base,'simulation':simulation,'hybrid':hybrid,'hybrid_mc_se':se,'wins':wins,
            'unresolved_trials':unresolved,'unresolved_fraction':unresolved/n,'mean_events':events/n,
            'transitions':transitions,'effective_hybrid_weight':alpha,'minimum_history_met':active,
            'config':asdict(config),'derived_seed':seed,'inputs':inputs,
            'scope':'First points including free throws, conditional on these ten starters; research only'}


def prediction_rows(report,lineups):
    evidence={r['Player ID']:r for r in report['inputs']['evidence']}
    rows=[]
    for team,players in lineups.items():
        for player in players:
            pid=player['player_id'];se=report['hybrid_mc_se'][pid]
            rows.append({**evidence[pid],'Baseline %':100*report['baseline'][pid],
                         'Simulation %':100*report['simulation'][pid],'Hybrid %':100*report['hybrid'][pid],
                         'Hybrid minus baseline pp':100*(report['hybrid'][pid]-report['baseline'][pid]),
                         'Monte Carlo SE pp':100*se,'Simulated first scores':report['wins'][pid]})
    return sorted(rows,key=lambda r:(-r['Hybrid %'],r['Team'],r['Player ID']))


def backtest(history,min_training=100,config=None,progress=lambda message:None):
    """Walk forward by entire dates, using a fixed config. No current APIs or fitting."""
    from research_tools import audit, history_window, fingerprint, evaluation_metrics, top_k_credit, compare_evaluations
    config=(config or SimulationConfig(trials=2000)).validate()
    if type(min_training) is not int or min_training<1:raise ValueError('Training minimum must be a positive integer.')
    valid,issues=audit(history);byday=defaultdict(lambda:defaultdict(list))
    for row in valid:byday[row['date']][row['game_id']].append(row)
    prior=[];details={'Baseline':[],'Hybrid MC':[]};diagnostics=[]
    for day in sorted(byday):
        train=history_window(prior,day);training_games=len({r['game_id'] for r in train})
        if training_games>=min_training:
            progress('Simulating historical date '+day)
            for gid,rows in sorted(byday[day].items()):
                lineups={t:[r for r in rows if r['team']==t] for t in sorted({r['team'] for r in rows})}
                result=simulate(train,lineups,day,config)
                winner=next(r['player_id'] for r in rows if int(r['first_scorer']))
                for model,key in (('Baseline','baseline'),('Hybrid MC','hybrid')):
                    probs=result[key];wp=probs[winner]
                    details[model].append({'Date':day,'Game':gid,'Winner ID':winner,'Winner probability':wp,
                        'Top-1 credit':top_k_credit(probs,winner,1),'Top-3 credit':top_k_credit(probs,winner,3),
                        'Log loss':-math.log(wp) if wp>0 else math.inf,
                        'Brier':sum((p-int(pid==winner))**2 for pid,p in probs.items()),'Training games':training_games})
                diagnostics.append({'Date':day,'Game':gid,'Effective hybrid weight':result['effective_hybrid_weight'],
                                    'Unresolved trials':result['unresolved_trials'],'Trials':config.trials,
                                    'Last training date':result['inputs']['last_training_date'],
                                    'Training fingerprint':result['inputs']['history_fingerprint']})
        prior.extend(row for rows in byday[day].values() for row in rows)
    days=sorted({r['Date'] for r in details['Baseline']});newest=set(days[-max(1,math.ceil(len(days)/4)):]) if days else set()
    active={r['Game'] for r in diagnostics if r['Effective hybrid weight']>0}
    summary=[];comparisons=[]
    for period in ('All evaluated dates','Newest quarter of dates','Active hybrid games'):
        subsets={m:[r for r in rows if period=='All evaluated dates' or (period=='Newest quarter of dates' and r['Date'] in newest) or (period=='Active hybrid games' and r['Game'] in active)] for m,rows in details.items()}
        for model,rows in subsets.items():
            if rows:summary.append({'Period':period,'Model':model,'Dates':len({r['Date'] for r in rows}),**evaluation_metrics(rows)})
        # Pure MC can assign zero counts; retain such misses and withhold undefined
        # log-loss differences instead of deleting games or adding a post-hoc floor.
        finite=all(math.isfinite(r['Log loss']) for rows in subsets.values() for r in rows)
        metrics=('Log loss','Brier','Top-1 credit','Top-3 credit') if finite else ('Brier','Top-1 credit','Top-3 credit')
        paired=compare_evaluations({'games':subsets['Baseline']},{'games':subsets['Hybrid MC']},metrics=metrics)
        comparisons.extend({'Period':period,'Games':paired['games'],'Dates':paired['dates'],**r} for r in paired['metrics'])
        if not finite:comparisons.append({'Period':period,'Metric':'Log loss','Note':'Non-finite loss retained; paired log-loss interval withheld.'})
    return {'fingerprint':fingerprint(history),'config':asdict(config),'min_training':min_training,
            'summary':summary,'comparisons':comparisons,'details':[{'Model':m,**r} for m,rows in details.items() for r in rows],
            'diagnostics':diagnostics,'excluded':issues,'evaluated_games':len(details['Baseline'])}


def main():
    """Offline evaluation entry point; never syncs data or accesses API keys."""
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Compare V3 hybrid Monte Carlo with Baseline on saved history.')
    parser.add_argument('--history',type=Path,default=eng.HISTORY)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--min-training',type=int,default=100)
    parser.add_argument('--trials',type=int,default=2000)
    parser.add_argument('--seed',type=int,default=3000)
    parser.add_argument('--weight',type=float,default=.35)
    args=parser.parse_args()
    if not args.history.is_file():parser.error('History file does not exist. Import or copy your saved history first.')
    try:
        report=backtest(eng.read_csv(args.history),args.min_training,SimulationConfig(trials=args.trials,seed=args.seed,hybrid_weight=args.weight),print)
    except ValueError as exc:parser.error(str(exc))
    def safe(value):
        if isinstance(value,float) and not math.isfinite(value):return None
        if isinstance(value,dict):return {k:safe(v) for k,v in value.items()}
        if isinstance(value,list):return [safe(v) for v in value]
        return value
    report['json_note']='Non-finite losses are null in JSON; affected paired log-loss comparisons are explicitly withheld.'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(safe(report),indent=2,allow_nan=False),encoding='utf-8')
    print(f"Evaluated {report['evaluated_games']} games. Report: {args.output}")


if __name__=='__main__':main()
