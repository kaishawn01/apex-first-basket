"""Replay cache import without altering the real ledger or frozen February evaluation."""
import sys,json,tempfile,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import phase5_integrity as audit,phase4_data as data
paths=[ROOT/'data/v3_validation',ROOT/'data/phase3_validation',ROOT/'data/phase4/raw']
protected=[ROOT/'validation/PHASE4_RESULTS.json',ROOT/'data/phase4/frozen_forecasts.json']
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
current=audit.reconcile(ROOT/'data/phase4',paths)
sources,errors=audit.inventory(paths)
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder)
 for gid,items in sorted(sources.items()):
  if len({x['hash'] for x in items})!=1:continue
  data.ingest(items[0]['game'],items[0]['wrapper'],root)
 replay=audit.reconcile(root,paths)
 assert replay['healthy'],replay
 after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
 assert before==after
report={'at':datetime.now(timezone.utc).isoformat(),'current':current,'isolated_replay':{k:replay[k] for k in ['database_games_before','unique_raw_games','healthy','still_missing','receipted_games','import_receipt_errors']},'frozen_artifact_sha256':before,'frozen_artifacts_unchanged':before==after,'phase4_discrepancy_explained':False,'finding':'Preserved logs report 690 seeded plus 420 additions, but original ledger inventory contained 1102. Eight intact caches were restored in Phase 4. No per-import receipts or independent database snapshot existed then. Current replay imports all 1110 games with matching atomic receipts and no missing IDs. No deletion path was found in the collector. This does not uniquely identify the original cause.','recovery_tests':'Interrupted transaction rollback, terminated process rollback, duplicate concurrent import, missing-cache reconciliation, conflicting-source refusal and checkpoint receipt checks are automated.'}
(ROOT/'validation/PHASE5_INTEGRITY_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='current'},indent=2))
