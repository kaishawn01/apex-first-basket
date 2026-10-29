"""Batch interface: fixture/manual/scheduled/validation, no Streamlit process."""
import argparse,json,os,tempfile
from pathlib import Path
from datetime import datetime,timezone
import phase6_cloud as cloud
from phase6_journal import Journal
from phase5_store import Store
from phase6_fixture import exercise

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['fixture-generate','fixture-grade','manual','scheduled','validation']);p.add_argument('--journal',required=True);p.add_argument('--training-file');p.add_argument('--day');p.add_argument('--data-root');a=p.parse_args()
    if os.environ.get('APEX_AUTOMATION_DISABLED')=='true':raise ValueError('Global disable switch is on')
    if a.mode.startswith('fixture-'):report=exercise(a.journal,a.mode.removeprefix('fixture-'))
    else:
        if os.environ.get('APEX_LIVE_COLLECTION_APPROVED')!='true':raise ValueError('Live collection not approved; no provider calls made')
        j=Journal(a.journal)
        if os.environ.get('GITHUB_ACTIONS')=='true':
            if os.environ.get('GITHUB_RUN_ATTEMPT','1')!='1':raise ValueError('Live retries require a new run and fresh quota reservation')
            if not a.data_root:raise ValueError('Cloud runs require durable data checkout')
            from phase6_git import publish
            cloud.register(j);cloud.reserve_budget(j,os.environ['GITHUB_RUN_ID'])
            publish(Path(a.data_root),str(Path(a.journal).resolve().relative_to(Path(a.data_root).resolve())))
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'operations.db')
            report=cloud.run(j,a.mode,training=cloud.load_training(a.training_file) if a.mode!='validation' else None,store=store,day=a.day,enabled=True)
    print(json.dumps(report,indent=2))
    if report.get('status') in ('failed','partial'):raise SystemExit(1)
if __name__=='__main__':main()
