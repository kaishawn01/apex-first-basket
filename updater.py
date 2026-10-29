"""Explicit, pinned-commit updates for the public APEX repository. Standard library only."""
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT=Path(__file__).resolve().parent
REPO='kaishawn01/apex-first-basket'
BRANCH='main'
MAX_FILE=2_000_000
ALLOWED=frozenset(('test_phase9.py','PHASE9_ENTITLEMENTS.md','PHASE9_HISTORICAL_SOURCES.md','PHASE9_DATA_MIGRATION.md','phase8_access.py','phase8_fixture.py','phase8_ui.py','test_phase8.py','PHASE8_DATA_ACCESS.md','PHASE8_LIVE_OPERATIONS.md','phase7_training.py','phase7_live.py','phase7_fixture.py','phase7_ui.py','test_phase7.py','PHASE7_LIVE.md','phase6_journal.py','phase6_cloud.py','phase6_metrics.py','phase6_fixture.py','phase6_git.py','phase6_cli.py','phase6_ui.py','phase6_smoke.py','test_phase6.py','PHASE6_CLOUD.md','app.py','dashboard_core.py','first_basket_engine.py','research_tools.py',
 'updater.py','launcher.py','START_APEX.bat','RESTORE_APEX.bat','requirements.txt','README.md',
 'START_HERE.txt','VERSION','test_engine.py','test_dashboard.py','test_research.py','test_updater.py',
 'phase5_store.py','phase5_integrity.py','phase5_providers.py','phase5_protocol.py','phase5_runner.py','phase5_ui.py','test_phase5.py','test_phase5_postgres.py','PHASE5_OPERATIONS.md','phase4_data.py','phase4_forward.py','phase4_research.py','phase4_ui.py','test_phase4.py','phase3.py','outcome_data.py','test_phase3.py','phase2.py','opening_data.py','test_phase2.py','simulation.py','test_simulation.py','V3_REVIEW.md','ui_smoke.py','espn_test_fixture.json','GITHUB_SETUP.txt','build_manifest.py','.gitignore'))
REQUIRED={'app.py','dashboard_core.py','first_basket_engine.py','research_tools.py','updater.py','launcher.py','START_APEX.bat','requirements.txt','VERSION'}


def version(text):
    if not isinstance(text,str) or not re.fullmatch(r'\d+\.\d+\.\d+',text):
        raise ValueError('Invalid release version.')
    return tuple(map(int,text.split('.')))


def current_version(root=ROOT):
    return (root/'VERSION').read_text().strip() if (root/'VERSION').exists() else '2.1.0'


def fetch(url):
    import ssl
    import certifi
    try:
        with urlopen(Request(url,headers={'User-Agent':'APEX-Updater/2.2','Accept':'application/vnd.github+json'}),timeout=30, context=ssl.create_default_context(cafile=certifi.where())) as response:
            body=response.read(MAX_FILE+1)
        if len(body)>MAX_FILE: raise ValueError('Update file exceeds allowed size.')
        return body
    except HTTPError as exc:
        if exc.code==404: raise RuntimeError('GitHub update files are not published yet. Complete the initial upload first.') from None
        if exc.code in (403,429): raise RuntimeError('GitHub denied or rate-limited this request. Try again later.') from None
        raise RuntimeError(f'GitHub returned HTTP {exc.code}. No update installed.') from None
    except (URLError,TimeoutError,OSError):
        raise RuntimeError('Cannot reach GitHub. Your installed app is unchanged.') from None


def validate_manifest(manifest):
    version(manifest.get('version'))
    files=manifest.get('files')
    if not isinstance(files,dict) or not REQUIRED.issubset(files): raise ValueError('Incomplete update manifest.')
    if version(manifest['version'])>=(3,0,0) and 'simulation.py' not in files:raise ValueError('V3 update is missing the simulation module.')
    if version(manifest['version'])>=(3,0,1) and not {'phase2.py','opening_data.py'}.issubset(files):raise ValueError('Phase 2 update is missing empirical research modules.')
    if version(manifest['version'])>=(3,0,2) and not {'phase3.py','outcome_data.py'}.issubset(files):raise ValueError('Phase 3 update is missing complete-outcome research modules.')
    if version(manifest['version'])>=(3,0,4) and not {'phase5_store.py','phase5_integrity.py','phase5_providers.py','phase5_protocol.py','phase5_runner.py','phase5_ui.py'}.issubset(files):raise ValueError('Phase 5 modules missing.')
    if version(manifest['version'])>=(3,0,3) and not {'phase4_data.py','phase4_forward.py','phase4_research.py','phase4_ui.py'}.issubset(files):raise ValueError('Phase 4 modules missing.')
    if version(manifest['version'])>=(3,0,5) and not {'phase6_journal.py','phase6_cloud.py','phase6_metrics.py','phase6_cli.py','phase6_ui.py','phase6_fixture.py','phase6_git.py'}.issubset(files):raise ValueError('Phase 6 modules missing.')
    if version(manifest['version'])>=(3,0,6) and not {'phase7_training.py','phase7_live.py','phase7_fixture.py','phase7_ui.py'}.issubset(files):raise ValueError('Phase 7 modules missing.')
    if version(manifest['version'])>=(3,0,7) and not {'phase8_access.py','phase8_fixture.py','phase8_ui.py'}.issubset(files):raise ValueError('Phase 8 modules missing.')
    if not set(files).issubset(ALLOWED): raise ValueError('Update contains an unexpected or protected filename.')
    for name,digest in files.items():
        if not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest): raise ValueError('Invalid file checksum.')
    return manifest


def check(root=ROOT):
    commit=json.loads(fetch(f'https://api.github.com/repos/{REPO}/commits/{BRANCH}'))['sha']
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Invalid GitHub commit ID.')
    base=f'https://raw.githubusercontent.com/{REPO}/{commit}/'
    manifest=validate_manifest(json.loads(fetch(base+'update_manifest.json')))
    return {'commit':commit,'manifest':manifest,'available':version(manifest['version'])>version(current_version(root))}


def stage(release,root=ROOT):
    manifest=validate_manifest(release['manifest'])
    commit=release['commit']
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Invalid commit.')
    if version(manifest['version'])<=version(current_version(root)):raise ValueError('This version is already installed or older.')
    pending=root/'.apex_pending'
    if pending.exists():raise ValueError('An update is already prepared. Restart APEX to install it.')
    with tempfile.TemporaryDirectory(prefix='.apex_download_',dir=root) as folder:
        stage_path=Path(folder)
        for name,digest in manifest['files'].items():
            content=fetch(f'https://raw.githubusercontent.com/{REPO}/{commit}/{name}')
            if hashlib.sha256(content).hexdigest()!=digest:raise ValueError(f'Checksum mismatch for {name}. No update installed.')
            (stage_path/name).write_bytes(content)
        if (stage_path/'VERSION').read_text().strip()!=manifest['version']:raise ValueError('Version file does not match manifest.')
        (stage_path/'update_manifest.json').write_text(json.dumps(manifest))
        (stage_path/'ready.json').write_text(json.dumps({'commit':commit,'version':manifest['version']}))
        # Publish a complete staging directory only after every file verifies.
        os.replace(stage_path,pending)
    return manifest['version']


def verify_pending(pending):
    manifest=validate_manifest(json.loads((pending/'update_manifest.json').read_text()))
    if not (pending/'ready.json').exists():raise ValueError('Update preparation is incomplete.')
    for name,digest in manifest['files'].items():
        path=pending/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Prepared file {name} failed verification.')
    if (pending/'VERSION').read_text().strip()!=manifest['version']:raise ValueError('Prepared version mismatch.')
    return manifest


def replace_copy(source,target):
    if target.is_symlink():raise ValueError('Refusing to replace a symbolic link.')
    temp=target.with_name(target.name+'.apex_tmp')
    shutil.copyfile(source,temp)
    os.replace(temp,target)


def restore_backup(backup,root):
    records=json.loads((backup/'backup.json').read_text())
    if not set(records).issubset(ALLOWED|{'update_manifest.json'}):raise ValueError('Invalid backup filenames.')
    for name,existed in records.items():
        if existed:replace_copy(backup/name,root/name)
        elif (root/name).exists():(root/name).unlink()


def apply_pending(root=ROOT):
    pending=root/'.apex_pending'
    if not pending.exists():return None
    manifest=verify_pending(pending)
    if version(manifest['version'])<=version(current_version(root)):raise ValueError('Pending update is not newer than the installed version.')
    backup=root/'.apex_backup'
    # All program backups must complete before any program file is changed.
    with tempfile.TemporaryDirectory(prefix='.apex_backup_build_',dir=root) as folder:
        build=Path(folder);records={}
        for name in list(manifest['files'])+['update_manifest.json']:
            path=root/name
            if path.is_symlink():raise ValueError('Program file is a symbolic link; update stopped.')
            records[name]=path.exists()
            if path.exists():shutil.copyfile(path,build/name)
        (build/'backup.json').write_text(json.dumps(records))
        if backup.exists():shutil.rmtree(backup)
        os.replace(build,backup)
    try:
        for name in list(manifest['files'])+['update_manifest.json']:
            replace_copy(pending/name,root/name)
    except Exception:
        restore_backup(backup,root)
        raise
    shutil.rmtree(pending)
    # A changed dependency file will trigger installation on next launch.
    return manifest['version']


def rollback(root=ROOT):
    backup=root/'.apex_backup'
    if not backup.exists():raise ValueError('No previous program backup is available.')
    restore_backup(backup,root)
    pending=root/'.apex_pending'
    if pending.exists():shutil.rmtree(pending)
    return current_version(root)


def auto_stage(root=ROOT):
    """Called under the launcher lock, before Streamlit starts."""
    if (root/'.apex_pending').exists():
        return
    try:
        release=check(root)
        if release['available']:
            print('Downloading APEX '+release['manifest']['version']+'…', flush=True)
            stage(release, root)
        else:
            print('APEX is up to date.', flush=True)
    except Exception as exc:
        print('Automatic update unavailable: '+str(exc)+' Opening installed version.', flush=True)


if __name__=='__main__':
    import sys
    if '--auto-stage' in sys.argv:
        auto_stage()
