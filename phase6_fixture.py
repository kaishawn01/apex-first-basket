"""Explicit synthetic cloud integration exercise. Never a live prediction."""
import json,copy,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import requests
import outcome_data,phase4_data as data,phase6_cloud as cloud
from phase6_journal import Journal
from phase5_store import Store
from phase5_providers import ProviderError,stamp
import first_basket_engine as eng

class FixtureProviders:
    def __init__(self,clock,game=None):
        self.clock=clock;self.raw=json.loads((eng.ROOT/'espn_test_fixture.json').read_text());c=self.raw['header']['competitions'][0]
        self.raw['header']['id']='401809955';self.raw['header']['season']={'year':2027,'type':2};c.update(id='401809955',date=(clock()+timedelta(minutes=10)).isoformat(),status={'type':{'completed':True}})
        if game:c['date']=game['start_time']
        self.game=outcome_data.game_from_payload(self.raw);self.game['gameStatus']=1
        outcome=outcome_data.extract(self.game,self.raw)
        self.rosters={t:[{'player_id':r['player_id'],'player':r['player']} for r in outcome['rows'] if r['team']==t] for t in {r['team'] for r in outcome['rows']}}
    def schedule(self,day,fresh=False):return [copy.deepcopy(self.game)],{'retrieved_at':self.clock().isoformat()}
    def roster(self,team):return copy.deepcopy(self.rosters[team]),{'retrieved_at':self.clock().isoformat(),'sha256':'synthetic-fixture'}
    def injuries(self):raise ProviderError('Fixture: injury provider intentionally unavailable')
    def lineups(self,day):
        teams={}
        for side,tid in [('awayTeam',100),('homeTeam',200)]:
            team=self.game[side]['teamTricode'];teams[side]={'teamAbbreviation':team,'teamId':tid,'players':[{'personId':tid+i,'teamId':tid,'playerName':p['player'],'lineupStatus':'Expected','rosterStatus':'Active','position':pos,'timestamp':self.clock().isoformat()} for i,(p,pos) in enumerate(zip(self.rosters[team],('PG','SG','SF','PF','C')))]}
        raw={'games':[{'gameId':'0022600001','gameStatus':1,**teams}]}
        return [{'provider':'NBA','payload':raw,'retrieved_at':self.clock().isoformat(),'sha256':data.digest(raw)}],[]
    def result(self,gid):return {'payload':self.raw,'sha256':data.digest(self.raw),'retrieved_at':self.clock().isoformat()}

def exercise(path,action):
    j=Journal(path);old=j.rows('prediction')
    with tempfile.TemporaryDirectory() as tmp,patch.object(requests,'get',side_effect=AssertionError('Fixture must not call provider network')):
        if action=='generate':
            if old:return {'test_only':True,'generated':0,'duplicate_prevented':True,'head':j.read()['head']}
            clock=lambda:datetime.now(timezone.utc);p=FixtureProviders(clock);store=Store(Path(tmp)/'fixture.db',clock=clock)
            pred,added=cloud.generate(j,store,p,p.game,([],{},{}),'checkpoint-10','fixture',test=True)
            before=j.read();again,added2=cloud.generate(j,store,p,p.game,([],{},{}),'checkpoint-10','fixture',test=True)
            assert added and not added2 and again==pred and before==j.read()
            return {'test_only':True,'generated':1,'model_version':pred['payload']['model_version'],'duplicate_prevented':True,'forecast_hash':pred['hash'],'generated_at':pred['payload']['generated_at'],'head':j.read()['head']}
        if not old:raise ValueError('No persisted fixture prediction to grade')
        # Synthetic completed outcome and simulated later clock explicitly remain fixture-only.
        clock=lambda:stamp(old[0]['payload']['game']['start_time'])+timedelta(hours=4)
        j.clock=clock;p=FixtureProviders(clock,old[0]['payload']['game']);before=copy.deepcopy(j.rows('prediction'))
        result=cloud.grade(j,p,test=True);again=cloud.grade(j,p,test=True)
        assert before==j.rows('prediction') and again['graded']==0
        return {'test_only':True,**result,'immutable_prediction_preserved':True,'head':j.read()['head']}
