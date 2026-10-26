"""Owns a process lock while APEX runs. Updates are applied only when closed."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import updater

ROOT=Path(__file__).resolve().parent


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
                print('Restored APEX '+updater.rollback(ROOT));return 0
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
                return subprocess.call([str(python),'-m','streamlit','run','app.py','--server.address','127.0.0.1','--server.port','8501','--browser.gatherUsageStats','false','--server.fileWatcherType','none'],env={**os.environ,'PYTHONIOENCODING':'utf-8'})
        except Exception as exc:
            print(f'APEX could not start: {exc}\nIf an update failed, close APEX and run RESTORE_APEX.bat.')
            return 1
    return subprocess.call([sys.executable,str(ROOT/'launcher.py')])

if __name__=='__main__':sys.exit(main())
