"""Owns a process lock while APEX runs. Updates are applied only when closed."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import updater

ROOT=Path(__file__).resolve().parent


def prepare_startup_update(python, root=ROOT):
    """Download in the app environment; bound startup delay and fail open."""
    if (root/'.apex_auto_update_disabled').exists() or '--skip-auto-update' in sys.argv:
        return
    print('Checking for APEX updates…', flush=True)
    try:
        subprocess.run([str(python), str(root/'updater.py'), '--auto-stage'],
                       cwd=root, timeout=90, check=True,
                       env={**os.environ, 'PYTHONIOENCODING':'utf-8'})
    except (subprocess.SubprocessError, OSError):
        print('Update check did not finish. Opening the installed version.', flush=True)


def main():
    os.chdir(ROOT)
    with (ROOT/'.apex_running.lock').open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell()==0:
            lock.write(b'0');lock.flush()
        lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            print('APEX is already running. Close its command window before updating or restoring.')
            return 1
        try:
            if '--restore' in sys.argv:
                restored=updater.rollback(ROOT)
                (ROOT/'.apex_auto_update_disabled').touch()
                print('Restored APEX '+restored+'. Automatic updates paused.');return 0
            updated=updater.apply_pending(ROOT)
            if updated:
                print('Installed APEX '+updated+'. Starting the updated launcher…',flush=True)
                # Release the lock before re-entering; load updated launcher code.
                restart=True
            else:restart=False
            if not restart:
                python=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
                if not python.exists():subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True)
                requirement_hash=hashlib.sha256((ROOT/'requirements.txt').read_bytes()).hexdigest()
                marker=ROOT/'.venv'/'apex-requirements.sha256'
                if not marker.exists() or marker.read_text()!=requirement_hash:
                    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)
                    marker.write_text(requirement_hash)
                prepare_startup_update(python)
                updated=updater.apply_pending(ROOT)
                if updated:
                    print('Installed APEX '+updated+'. Restarting launcher…',flush=True)
                else:
                    return subprocess.call([str(python),'-m','streamlit','run','app.py','--server.address','127.0.0.1','--server.port','8501','--browser.gatherUsageStats','false','--server.fileWatcherType','none'],env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        except Exception as exc:
            print(f'APEX could not start: {exc}\nIf an update failed, close APEX and run RESTORE_APEX.bat.')
            return 1
    return subprocess.call([sys.executable,str(ROOT/'launcher.py'),'--skip-auto-update'])

if __name__=='__main__':sys.exit(main())
