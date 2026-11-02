"""Deterministic, allowlisted training candidates. No upload or permission inference."""
import json,sqlite3,hashlib,gzip,re
from pathlib import Path
from datetime import date,datetime,timezone
import first_basket_engine as eng,research_tools as rt,opening_data as od
from phase4_data import canonical,digest
from phase5_providers import stamp

ROW_FIELDS=tuple(eng.FIELDS)
SEQ_FIELDS=('schema','game_id','date','start_time','history_identity','starters','tip','events','lineup_verification','substitution_before_first_score','warnings')
EVENT_FIELDS={'kind','team','player','value','made','category','first_team_shot','second_chance','offensive','trip_start','shots'}
RECORD_FIELDS=('schema','game_id','date','start_time','status','scorer_id','starter_status','score_type','rows')
MAX_BYTES=25_000_000

def selected(value,names):return {k:value[k] for k in names if k in value}

def build(path,cutoff):
    target=date.fromisoformat(cutoff);path=Path(path).resolve();history=[];seqs={};records={};sources={};excluded=[];dropped=set()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Historical database integrity failure')
        source_rows=c.execute('SELECT gid,record,sequence,raw_hash FROM games ORDER BY gid').fetchall()
    for gid,raw,seq,h in source_rows:
        r=json.loads(raw);age=(target-date.fromisoformat(r['date'])).days
        if r['game_id']!=gid or r.get('source',{}).get('raw_hash')!=h:raise ValueError('Historical identity/source mismatch')
        if not 0<age<=400:excluded.append({'game':gid,'reason':'outside strictly earlier 400-day window'});continue
        clean=selected(r,RECORD_FIELDS);clean['rows']=[selected(x,ROW_FIELDS) for x in r.get('rows',[])]
        for x in r.get('rows',[]):dropped.update(set(x)-set(ROW_FIELDS))
        records[gid]=clean;sources[gid]=selected(r.get('source',{}),('provider','retrieved_at','provider_date','raw_hash'))
        if r['status']=='resolved' and r.get('rows') and sum(int(x['first_scorer']) for x in r['rows'])==1:
            valid,issues=rt.audit(clean['rows'])
            if issues:raise ValueError('Invalid historical starter training rows')
            history.extend(valid)
        if seq:
            s=json.loads(seq);out=selected(s,SEQ_FIELDS);out['events']=[selected(x,EVENT_FIELDS) for x in s['events']];out['warnings']=[]
            if s['game_id']!=gid or s['date']!=r['date']:raise ValueError('Sequence identity mismatch')
            seqs[gid]=out
    data={'history':history,'sequences':seqs,'records':records}
    bundle={'schema':2,'cutoff_exclusive':cutoff,'window_days':400,'test_only':False,'publication_approved':False,'rights_status':'unreviewed — public access is not a permission grant','data':data,'provenance':sources,'sha256':digest(data),'provenance_sha256':digest(sources)}
    validate(bundle)
    encoded=canonical(bundle).encode()
    report={'source_games':len(source_rows),'window_games':len(records),'validated_first_scores':sum(r['status']=='resolved' for r in records.values()),'training_games':len({r['game_id'] for r in history}),'history_rows':len(history),'usable_sequences':len(seqs),'ambiguous_games':sum(r['status']!='resolved' for r in records.values()),'excluded_games':len(excluded),'excluded_reason_counts':{'outside strictly earlier 400-day window':len(excluded)},'dropped_private_or_unknown_row_fields':sorted(dropped),'bytes':len(encoded),'gzip_bytes':len(gzip.compress(encoded,mtime=0)),'bundle_sha256':hashlib.sha256(encoded).hexdigest(),'data_sha256':bundle['sha256'],'provenance_sha256':bundle['provenance_sha256'],'cutoff_exclusive':cutoff,'publication_approved':False,'minimum_model_fields':list(ROW_FIELDS),'source_providers':sorted({s.get('provider','unknown') for s in sources.values()})}
    return bundle,report

def validate(b,target_day=None):
    if set(b)!={'schema','cutoff_exclusive','window_days','test_only','publication_approved','rights_status','data','provenance','sha256','provenance_sha256'} or b['schema']!=2 or b['window_days']!=400 or type(b['test_only']) is not bool:raise ValueError('Invalid training schema')
    if len(canonical(b).encode())>MAX_BYTES:raise ValueError('Training size limit')
    if digest(b['data'])!=b['sha256'] or digest(b['provenance'])!=b['provenance_sha256']:raise ValueError('Training/provenance checksum mismatch')
    cutoff=date.fromisoformat(b['cutoff_exclusive'])
    if target_day and cutoff>date.fromisoformat(target_day):raise ValueError('Bundle cutoff is later than forecast day')
    d=b['data']
    if set(d)!={'history','sequences','records'}:raise ValueError('Unexpected training fields')
    _,issues=rt.audit(d['history'])
    if issues:raise ValueError('Training history identity validation failed')
    ids=set()
    for r in d['history']:
        if set(r)-set(ROW_FIELDS):raise ValueError('Unapproved history fields')
        if (r['game_id'],r['player_id']) in ids:raise ValueError('Duplicate player/game row')
        ids.add((r['game_id'],r['player_id']))
        record=d['records'].get(r['game_id'])
        if not record or r not in record['rows']:raise ValueError('History/outcome mismatch')
    for gid,r in d['records'].items():
        if set(r)-set(RECORD_FIELDS) or gid!=r['game_id'] or not 0<(cutoff-date.fromisoformat(r['date'])).days<=400:raise ValueError('Record fields, identity or cutoff invalid')
        if r['status'] not in ('resolved','ambiguous'):raise ValueError('Unknown outcome state')
        if r['status']=='resolved' and (not str(r['scorer_id']).isdigit() or int(r['scorer_id'])<=0):raise ValueError('Invalid scorer identity')
        rows=r['rows'];ids=[x.get('player_id') for x in rows]
        if rows and (len(rows)!=10 or len(set(ids))!=10 or any(not str(x).isdigit() or int(x)<=0 for x in ids)):raise ValueError('Invalid outcome lineup identities')
        for row in rows:
            if set(row)-set(ROW_FIELDS) or row.get('game_id')!=gid or row.get('date')!=r['date']:raise ValueError('Unapproved outcome row fields or date identity')
        source=b['provenance'].get(gid,{})
        if set(source)-{'provider','retrieved_at','provider_date','raw_hash'} or source.get('provider')!='ESPN' or not re.fullmatch('[0-9a-f]{64}',source.get('raw_hash','')):raise ValueError('Missing or invalid source provenance')
        if source.get('retrieved_at'):stamp(source['retrieved_at'])
    if set(b['provenance'])!=set(d['records']):raise ValueError('Provenance inventory differs')
    for gid,s in d['sequences'].items():
        if gid not in d['records'] or set(s)-set(SEQ_FIELDS):raise ValueError('Sequence inventory/fields invalid')
        if any(set(e)-EVENT_FIELDS for e in s['events']):raise ValueError('Unapproved sequence event fields')
        rows=d['records'][gid]['rows']
        if not od.valid_for_history(s,rows):raise ValueError('Sequence is inconsistent with historical identities')
    return d['history'],d['sequences'],d['records']

def permission(bundle,grant,now=None):
    """Evidence gate, not legal certification. Human must verify provider permissions."""
    now=now or datetime.now(timezone.utc)
    if bundle['test_only'] or grant.get('test_only') is not False:raise ValueError('Fixture permission cannot authorize live data')
    if grant.get('schema')!=1 or grant.get('data_sha256')!=bundle['sha256'] or grant.get('provenance_sha256')!=bundle['provenance_sha256'] or grant.get('owner_approved') is not True:raise ValueError('Owner/bundle authorization absent')
    if stamp(grant['expires_at'])<=now or stamp(grant['reviewed_at'])>now:raise ValueError('Permission expired or future dated')
    required={'private_model_use','automated_collection','public_forecasts'}
    source=grant.get('providers',{}).get('ESPN',{})
    if source.get('permission_verified') is not True or not required<=set(source.get('scopes',[])) or not source.get('evidence_reference'):raise ValueError('Applicable provider permission evidence is missing')
    return grant

def load(path,grant_path,target_day):
    p=Path(path)
    if p.stat().st_size>MAX_BYTES:raise ValueError('Training size limit')
    b=json.loads(p.read_text());training=validate(b,target_day);g=permission(b,json.loads(Path(grant_path).read_text()));return b,training,g

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--cutoff',required=True);p.add_argument('--output',required=True);a=p.parse_args();b,r=build(a.database,a.cutoff)
    with Path(a.output).open('x') as f:f.write(canonical(b))
    print(json.dumps(r,indent=2))
