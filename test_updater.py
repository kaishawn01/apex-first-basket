import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import updater as u


def release():
    contents={name:b'new program\n' for name in u.REQUIRED}
    contents['VERSION']=b'2.3.0\n'
    manifest={'version':'2.3.0','files':{n:hashlib.sha256(b).hexdigest() for n,b in contents.items()}}
    return {'commit':'a'*40,'manifest':manifest,'available':True},contents


class UpdateTests(unittest.TestCase):
    def test_protected_files_rejected(self):
        for name in ('.apex_keys.json','data/history.csv','../app.py','odds.csv','folder/app.py'):
            r,_=release();r['manifest']['files'][name]='a'*64
            with self.assertRaises(ValueError):u.validate_manifest(r['manifest'])
    def test_incomplete_and_bad_checksum(self):
        r,_=release();del r['manifest']['files']['app.py']
        with self.assertRaises(ValueError):u.validate_manifest(r['manifest'])
        r,_=release();r['manifest']['files']['app.py']='wrong'
        with self.assertRaises(ValueError):u.validate_manifest(r['manifest'])
    def test_stage_apply_restore_preserves_personal_files(self):
        r,contents=release()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'VERSION').write_text('2.2.0');(root/'app.py').write_text('old program')
            (root/'.apex_keys.json').write_text('private');(root/'odds.csv').write_text('my prices');(root/'data').mkdir();(root/'data'/'history.csv').write_text('my history')
            with patch.object(u,'fetch',side_effect=lambda url:contents[url.rsplit('/',1)[1]]):u.stage(r,root)
            self.assertEqual((root/'app.py').read_text(),'old program')
            self.assertEqual(u.apply_pending(root),'2.3.0')
            self.assertEqual((root/'.apex_keys.json').read_text(),'private')
            self.assertEqual((root/'odds.csv').read_text(),'my prices')
            self.assertEqual((root/'data'/'history.csv').read_text(),'my history')
            self.assertEqual(u.rollback(root),'2.2.0')
            self.assertEqual((root/'app.py').read_text(),'old program')
            self.assertFalse((root/'research_tools.py').exists())
    def test_bad_download_never_published(self):
        r,_=release()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'VERSION').write_text('2.2.0')
            with patch.object(u,'fetch',return_value=b'corrupt'):
                with self.assertRaises(ValueError):u.stage(r,root)
            self.assertFalse((root/'.apex_pending').exists())
            self.assertEqual(u.current_version(root),'2.2.0')
    def test_tampered_pending_rejected(self):
        r,contents=release()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'VERSION').write_text('2.2.0')
            with patch.object(u,'fetch',side_effect=lambda url:contents[url.rsplit('/',1)[1]]):u.stage(r,root)
            (root/'.apex_pending'/'app.py').write_text('tampered')
            with self.assertRaises(ValueError):u.apply_pending(root)
            self.assertEqual(u.current_version(root),'2.2.0')
    def test_apply_failure_restores_previous_files(self):
        r,contents=release()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'VERSION').write_text('2.2.0')
            for name in u.REQUIRED-{'VERSION'}:(root/name).write_text('old')
            with patch.object(u,'fetch',side_effect=lambda url:contents[url.rsplit('/',1)[1]]):u.stage(r,root)
            original=u.replace_copy;calls=0
            def fail_once(src,dst):
                nonlocal calls
                calls+=1
                if calls==2:raise OSError('simulated write failure')
                return original(src,dst)
            with patch.object(u,'replace_copy',side_effect=fail_once):
                with self.assertRaises(OSError):u.apply_pending(root)
            self.assertEqual(u.current_version(root),'2.2.0')
            self.assertEqual((root/'app.py').read_text(),'old')
    def test_check_pins_manifest_to_commit(self):
        r,_=release()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'VERSION').write_text('2.2.0')
            with patch.object(u,'fetch',side_effect=[json.dumps({'sha':r['commit']}).encode(),json.dumps(r['manifest']).encode()]) as fetch:
                self.assertTrue(u.check(root)['available'])
            self.assertIn('/'+'a'*40+'/',fetch.call_args.args[0])

class StartupUpdateTests(unittest.TestCase):
    def test_auto_stages_new_release_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for available in (False,True):
                r,_=release();r['available']=available
                with patch.object(u,'check',return_value=r),patch.object(u,'stage') as stage:
                    u.auto_stage(root)
                    self.assertEqual(stage.call_count,int(available))
    def test_network_failure_keeps_installed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'VERSION').write_text('2.2.0')
            with patch.object(u,'check',side_effect=RuntimeError('offline')),patch.object(u,'stage') as stage:
                u.auto_stage(root);stage.assert_not_called()
            self.assertEqual(u.current_version(root),'2.2.0')
    def test_timeout_and_disabled_startup(self):
        import launcher
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(launcher.subprocess,'run',side_effect=launcher.subprocess.TimeoutExpired('update',90)) as run:
                launcher.prepare_startup_update(Path('python'),root)
                self.assertEqual(run.call_args.kwargs['timeout'],90)
            (root/'.apex_auto_update_disabled').touch()
            with patch.object(launcher.subprocess,'run') as run:
                launcher.prepare_startup_update(Path('python'),root);run.assert_not_called()
    def test_restart_does_not_check_again(self):
        import launcher
        with tempfile.TemporaryDirectory() as tmp,patch.object(launcher.sys,'argv',['launcher.py','--skip-auto-update']),patch.object(launcher.subprocess,'run') as run:
            launcher.prepare_startup_update(Path('python'),Path(tmp));run.assert_not_called()

if __name__=='__main__':unittest.main()
