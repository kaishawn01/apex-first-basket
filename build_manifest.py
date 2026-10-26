"""Run after editing program files and increasing VERSION, before GitHub upload."""
import hashlib
import json
from pathlib import Path
from updater import ALLOWED,validate_manifest
root=Path(__file__).resolve().parent
files={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(ALLOWED) if (root/name).is_file()}
manifest={'version':(root/'VERSION').read_text().strip(),'files':files}
validate_manifest(manifest)
(root/'update_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Manifest built for version '+manifest['version'])
