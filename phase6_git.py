"""Repository-native archive publication. Never force pushes or modifies code refs."""
import json,subprocess,os,re
from pathlib import Path
from datetime import datetime,timezone
from phase6_journal import Journal,validate
from phase5_providers import stamp

BRANCH='apex-research-data'
MAX_GIT_BYTES=50_000_000

def git(root,*args):
    r=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=60)
    if r.returncode:raise ValueError('Git operation failed; archive not confirmed. Preserve local work and retry from latest branch.')
    return r.stdout.strip()

def publish(root,relative):
    root=Path(root);path=root/relative
    if not re.fullmatch(r'(fixtures/[0-9a-f]{40}|live)/journal.json',relative):raise ValueError('Invalid archive path')
    if git(root,'branch','--show-current')!=BRANCH:raise ValueError('Refusing to write outside dedicated data branch')
    if sum(p.stat().st_size for p in (root/'.git').rglob('*') if p.is_file())>MAX_GIT_BYTES:raise ValueError('Git storage ceiling reached; migration review required')
    if any(p.is_symlink() for p in root.rglob('*') if '.git' not in p.parts):raise ValueError('Symlink in archive refused')
    if sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and '.git' not in p.parts)>25_000_000:raise ValueError('Archive file capacity reached; migrate before continuing')
    current=Journal(path).read()
    tracked=git(root,'ls-files',relative)
    if tracked:
        old=json.loads(git(root,'show','HEAD:'+relative));validate(old)
        if current['events'][:len(old['events'])]!=old['events']:raise ValueError('Archive rewrite rejected')
    git(root,'add','--',relative)
    if not git(root,'diff','--cached','--name-only'):
        return publish_report(root,relative,current,git(root,'rev-parse','HEAD'),False)
    # Never stage secrets, raw caches, or unrelated files from the runner.
    if git(root,'diff','--cached','--name-only').splitlines()!=[relative]:raise ValueError('Unexpected staged files')
    git(root,'-c','user.name=APEX research bot','-c','user.email=apex-research@users.noreply.github.com','commit','-m','Append labeled research evidence')
    commit=git(root,'rev-parse','HEAD')
    git(root,'push','origin','HEAD:refs/heads/'+BRANCH) # Fast-forward only; a race fails closed.
    remote=git(root,'ls-remote','origin','refs/heads/'+BRANCH).split()[0]
    if remote!=commit:raise ValueError('Publication not confirmed; do not report success')
    return publish_report(root,relative,current,commit,True)

def publish_report(root,relative,current,commit,changed):
    """Derivable view plus first observed remote-publication receipts; originals untouched."""
    if git(root,'ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=commit:raise ValueError('Remote branch changed before receipt')
    now=datetime.now(timezone.utc).isoformat();path=Path(relative).with_name('report.json');target=root/path
    old=json.loads(target.read_text()) if target.exists() else {};seen=old.get('receipts',{})
    history=receipts(root,relative)
    for r in current['events']:
        if r['kind']=='prediction' and r['hash'] not in seen:
            seen[r['hash']]={**history[r['hash']],'verified_remote_at':now}
    from phase6_metrics import evaluate
    j=Journal(root/relative);test=relative.startswith('fixtures/')
    report={'schema':1,'journal_head':current['head'],'publication_verified_at':now,'receipts':seen,'test_only':test,'automation_enabled':False,'evaluation':evaluate(j,seen,test=test)}
    # Do not add another report commit on a duplicate retry.
    if old and old['journal_head']==current['head'] and old.get('receipts')==seen:
        return {'commit':commit,'head':current['head'],'changed':changed,'persisted':True}
    target.write_text(json.dumps(report,sort_keys=True,allow_nan=False)+'\n')
    git(root,'add','--',path.as_posix())
    if git(root,'diff','--cached','--name-only').splitlines()!=[path.as_posix()]:raise ValueError('Unexpected report staging')
    git(root,'-c','user.name=APEX research bot','-c','user.email=apex-research@users.noreply.github.com','commit','-m','Record verified publication and derived research metrics')
    git(root,'push','origin','HEAD:refs/heads/'+BRANCH)
    final=git(root,'rev-parse','HEAD')
    if git(root,'ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=final:raise ValueError('Report publication not confirmed')
    return {'commit':final,'head':current['head'],'changed':changed,'persisted':True}

def receipts(root,relative):
    """Reconstruct first-containing commit times, verified against Git blobs."""
    root=Path(root);found={}
    for commit in git(root,'log','--reverse','--format=%H','--',relative).splitlines():
        doc=validate(json.loads(git(root,'show',commit+':'+relative)));at=git(root,'show','-s','--format=%cI',commit);stamp(at)
        for r in doc['events']:
            if r['kind']=='prediction':found.setdefault(r['hash'],{'commit':commit,'committed_at':at})
    return found

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['publish','verify']);p.add_argument('--root',required=True);p.add_argument('--file',required=True);a=p.parse_args()
    if a.action=='publish':report=publish(a.root,a.file)
    else:
        j=Journal(Path(a.root)/a.file);j.read()
        from phase6_metrics import evaluate
        report={'integrity':'verified','durable_receipts':receipts(a.root,a.file),'evaluation':evaluate(j,json.loads((Path(a.root)/a.file).with_name('report.json').read_text())['receipts'],test=a.file.startswith('fixtures/'))}
    print(json.dumps(report,indent=2))
