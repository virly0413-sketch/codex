import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import run
import filipino_latest_start as latest
from filipino_setup import bind_channel
from material_library import SETTINGS, set_material_folder
from publisher_profiles import available_profiles

REPO = run.ROOT
CHANNEL = 'UC' + 't' * 22  # Offline fixture only.


class LatestFilipinoTests(unittest.TestCase):
    def test_complete_zip_upgrade_reload_and_custom_folder(self):
        archive = REPO / 'releases/filipino_publisher_complete_22_latest_20261105_20261115_1080p.zip'
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                names = z.namelist()
                self.assertFalse(any('/profiles/' in n or '/local_work' in n or 'token.' in n or 'client_secret' in n for n in names))
                z.extractall(tmp)
            root = Path(tmp) / 'youtube_publisher_filipino'
            with patch.object(run, 'ROOT', root), patch.object(run, 'auth', side_effect=AssertionError('offline only')), contextlib.redirect_stdout(io.StringIO()):
                profile = bind_channel(CHANNEL)
                old = run.load(profile)
                old.update(proxy_url='', http_timeout_seconds=120, oauth_token='my-local-token.json')
                run.save(profile, old)
                receipt = root / 'local_work_old/receipt.json'
                run.save(receipt, {'keep': True})
                run.save(root / SETTINGS, {'es': 'untouched-spanish-folder'})
                path = latest.prepare_latest()
                config = run.load(path)
                self.assertEqual(config['material_job_count'], 22)
                self.assertEqual(config['oauth_token'], 'my-local-token.json')
                self.assertEqual(config['proxy_url'], '')
                jobs = run.load(root / config['planning_source'])
                self.assertEqual(jobs[0]['date'], '2026-11-05')
                self.assertEqual(jobs[-1]['date'], '2026-11-15')
                self.assertEqual({j['publish_local'][11:16] for j in jobs}, {'12:00', '17:00'})
                self.assertEqual(latest.prepare_latest(), path)
                choices = available_profiles(path)
                self.assertIn(str(path.resolve()), choices.values())
                custom = root / 'custom-tl'
                shutil.copytree(root / latest.PACK, custom)
                set_material_folder('tl', custom)
                shutil.rmtree(root / latest.PACK)
                self.assertEqual(latest.prepare_latest(), path)
                self.assertEqual(run.load(root / SETTINGS)['tl'], str(custom.resolve()))
                self.assertEqual(run.load(root / SETTINGS)['es'], 'untouched-spanish-folder')
                self.assertEqual(run.load(receipt), {'keep': True})


if __name__ == '__main__':
    unittest.main()
