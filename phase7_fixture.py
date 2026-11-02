"""Offline Phase 7 acceptance exercise, explicitly synthetic throughout."""
import tempfile,copy,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import requests
from phase6_fixture import FixtureProviders
from phase6_journal import Journal
from phase5_store import Store
from phase4_data import digest
import phase7_live as live

def empty_bundle(day):
    d={'history':[],'sequences':{},'records':{}}
    return {'schema':2,'cutoff_exclusive':day,'window_days':400,'test_only':True,'publication_approved':False,'rights_status':'synthetic fixture only','data':d,'provenance':{},'sha256':digest(d),'provenance_sha256':digest({})}

def exercise(path,action):
    j=Journal(path,clock=lambda:datetime(2027,1,2,21,tzinfo=timezone.utc));old=j.rows('prediction')
    with tempfile.TemporaryDirectory() as tmp,patch.object(requests,'get',side_effect=AssertionError('No live provider permitted in fixture')):
        if action=='generate':
            if old:return {'test_only':True,'generated':0,'duplicate_prevented':True}
            p=FixtureProviders(j.clock);s=Store(Path(tmp)/'store.db',clock=j.clock);b=empty_bundle(p.game['_date'])
            saved,added=live.generate(j,s,p,p.game,b,'checkpoint-10','fixture',test=True);_,again=live.generate(j,s,p,p.game,b,'checkpoint-10','fixture',test=True)
            assert added and not again
            return {'test_only':True,'generated':1,'duplicate_prevented':True,'model_version':saved['payload']['model_version']}
        if not old:raise ValueError('No persisted fixture')
        before=copy.deepcopy(j.rows('prediction'));j.clock=lambda:live.stamp(before[0]['payload']['game']['start_time'])+timedelta(hours=4);p=FixtureProviders(j.clock,before[0]['payload']['game'])
        r=live.cloud.grade(j,p,test=True);assert live.cloud.grade(j,p,test=True)['graded']==0;assert before==j.rows('prediction')
        return {'test_only':True,**r,'original_preserved':True}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['generate','grade']);p.add_argument('--journal',required=True);a=p.parse_args();print(json.dumps(exercise(a.journal,a.action),indent=2))
