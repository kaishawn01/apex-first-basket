"""Inventory reconciliation is independent of frozen model evaluations."""
import json,sqlite3,uuid
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timezone
import phase4_data as data,outcome_data

def inventory(directories):
    sources=defaultdict(list);errors=[]
    for directory in directories:
        for path in sorted(Path(directory).glob('espn_*.json')):
            try:
                w=json.loads(path.read_text());p=w.get('payload',w);g=outcome_data.game_from_payload(p)
                if g['gameId']!=path.stem:raise ValueError('Cache filename/game identity mismatch')
                h=data.digest(p)
                if 'payload' in w and w.get('sha256')!=h:raise ValueError('Raw cache checksum mismatch')
                sources[g['gameId']].append({'path':str(path),'hash':h,'wrapper':w if 'payload' in w else {'payload':p,'retrieved_at':None,'provider_date':None},'game':g})
            except Exception as exc:errors.append({'file':path.name,'reason':str(exc) if isinstance(exc,ValueError) else type(exc).__name__})
    return sources,errors

def reconcile(root,directories,repair=False):
    root=Path(root);sources,errors=inventory(directories);conflicts=[];duplicates=[];invalid=[];receipt_errors=[]
    with data.connect(root) as c:
        integrity=[r[0] for r in c.execute('PRAGMA integrity_check')]
        existing={gid:(json.loads(record),json.loads(seq) if seq else None,h) for gid,record,seq,h in c.execute('SELECT * FROM games')}
        receipts=list(c.execute('SELECT gid,raw_hash,receipt FROM import_receipts'))
    for gid,(r,s,h) in existing.items():
        if r.get('game_id')!=gid or r.get('source',{}).get('raw_hash')!=h:invalid.append({'game':gid,'reason':'Stored record identity/hash mismatch'})
        rows=r.get('rows',[]);ids=[x.get('player_id') for x in rows];teams=Counter(x.get('team') for x in rows)
        if rows and (len(ids)!=10 or len(set(ids))!=10 or any(not isinstance(x,str) or not x.isdigit() or int(x)<=0 for x in ids) or len(teams)!=2 or set(teams.values())!={5}):invalid.append({'game':gid,'reason':'Invalid ten-player identity/team partition'})
        if r.get('status')=='resolved' and (not str(r.get('scorer_id','')).isdigit() or int(r['scorer_id'])<=0):invalid.append({'game':gid,'reason':'Invalid scoring identity'})
    for gid,h,raw in receipts:
        x=json.loads(raw);item=existing.get(gid)
        if not item or h!=item[2] or x.get('record_hash')!=data.digest(item[0]) or x.get('sequence_hash')!=data.digest(item[1]):receipt_errors.append(gid)
    for gid,items in sources.items():
        hashes={x['hash'] for x in items}
        if len(items)>1:duplicates.append({'game':gid,'copies':len(items),'identical':len(hashes)==1})
        if len(hashes)>1 or (gid in existing and existing[gid][2] not in hashes):conflicts.append(gid)
    missing=sorted(set(sources)-set(existing));absent=sorted(set(existing)-set(sources));repaired=[]
    if repair:
        if integrity!=['ok'] or receipt_errors:raise ValueError('Repair refused: database integrity or import receipts failed')
        for gid in missing:
            if gid in conflicts:continue
            source=sources[gid][0]
            try:
                if data.ingest(source['game'],source['wrapper'],root):repaired.append(gid)
            except Exception as exc:errors.append({'game':gid,'reason':type(exc).__name__})
    report={'schema':1,'at':datetime.now(timezone.utc).isoformat(),'database_integrity':integrity,'database_games_before':len(existing),'unique_raw_games':len(sources),'raw_copies':sum(map(len,sources.values())),'missing_before':missing,'restored':repaired,'still_missing':sorted(set(missing)-set(repaired)),'database_without_raw':absent,'duplicate_cache_copies':duplicates,'conflicting_raw_games':conflicts,'invalid_records':invalid,'import_receipt_errors':sorted(set(receipt_errors)),'receipted_games':len({x[0] for x in receipts}),'legacy_without_receipts':len(set(existing)-{x[0] for x in receipts}),'errors':errors,'raw_manifest_hash':data.digest({gid:sorted({x['hash'] for x in items}) for gid,items in sources.items()}),'database_manifest_hash':data.digest({gid:r[2] for gid,r in existing.items()}),'frozen_evaluations_modified':False}
    report['healthy']=integrity==['ok'] and not any(report[k] for k in ['still_missing','database_without_raw','conflicting_raw_games','invalid_records','import_receipt_errors','errors'])
    target=root/'reconciliation';target.mkdir(parents=True,exist_ok=True)
    (target/(uuid.uuid4().hex+'.json')).write_text(data.canonical(report))
    return report

def sync_history(store,root):
    """Copy immutable modeled history and IDs into the configured evidence store."""
    added=0
    with data.connect(root) as c:
        rows=list(c.execute('SELECT gid,record,sequence,raw_hash FROM games ORDER BY gid'))
    for gid,raw,seq,h in rows:
        payload={'game_id':gid,'record':json.loads(raw),'sequence':json.loads(seq) if seq else None,'raw_hash':h}
        old=store.get('history',gid)
        if old and old['payload']!=payload:raise ValueError('Cloud history conflict; original retained')
        if not old:store.append('history',gid,payload);added+=1
    verified={r['payload']['game_id']:r['payload']['raw_hash'] for r in store.rows('history')}
    expected={gid:h for gid,raw,seq,h in rows}
    if any(verified.get(gid)!=h for gid,h in expected.items()):raise ValueError('Historical sync verification failed; do not collect forecasts')
    receipt={'added':added,'source_total':len(rows),'verified_total':len(verified),'manifest_hash':data.digest(verified)}
    store.append('history_sync',uuid.uuid4().hex,receipt)
    return receipt

def model_data(store):
    import research_tools as rt
    history=[];sequences={};records={}
    for event in store.rows('history'):
        p=event['payload'];gid=p['game_id'];r=p['record'];records[gid]=r
        if p['sequence']:sequences[gid]=p['sequence']
        if r['status']=='resolved' and r.get('rows') and sum(int(x['first_scorer']) for x in r['rows'])==1:
            valid,issues=rt.audit(r['rows'])
            if not issues:history.extend(valid)
    return history,sequences,records
