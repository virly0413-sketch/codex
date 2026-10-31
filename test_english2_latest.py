import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from PIL import Image
import run
import english2_latest_start as latest
from material_library import SETTINGS, set_material_folder
from publisher_profiles import available_profiles, remember_profile

REPO = run.ROOT


class English2LatestTests(unittest.TestCase):
    def test_complete_release_and_overlay_preserve_accounts_and_history(self):
        archive = REPO / 'releases/english2_publisher_complete_11_new_covers_titles_1080p.zip'
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                names = z.namelist()
                self.assertFalse(any('/profiles/' in n or '/local_work' in n or 'token.' in n or 'client_secret' in n for n in names))
                for name in ('run.py', 'english2_latest_start.py', 'material_library.py'):
                    self.assertEqual(z.read('youtube_publisher_english2/' + name), (REPO / name).read_bytes())
                z.extractall(tmp)
            root = Path(tmp) / 'youtube_publisher_english2'
            with patch.object(run, 'ROOT', root), patch.object(run, 'auth', side_effect=AssertionError('offline only')), contextlib.redirect_stdout(io.StringIO()):
                run.save(root / SETTINGS, {'en': 'english-one-untouched', 'tl': 'filipino-untouched'})
                profile = root / latest.PROFILE
                run.save(profile, {'channel_id': latest.CHANNEL, 'language': 'en', 'material_key': 'en2',
                                   'oauth_token': 'my-token.json', 'oauth_client': 'my-client.json',
                                   'proxy_url': '', 'http_timeout_seconds': 90})
                wrong = root / 'previous.json'
                run.save(wrong, {'channel_id': 'UC' + 'x' * 22, 'language': 'en', 'material_key': 'en', 'oauth_token': 'wrong-token.json'})
                remember_profile(wrong)
                receipt = root / 'local_work_old/receipt.json'
                run.save(receipt, {'keep': True})
                path = latest.prepare_latest()
                config = run.load(path)
                self.assertEqual(config['material_job_count'], 11)
                self.assertEqual(config['oauth_token'], 'my-token.json')
                self.assertEqual(config['oauth_client'], 'my-client.json')
                self.assertEqual(config['proxy_url'], '')
                self.assertEqual(config['http_timeout_seconds'], 90)
                jobs = run.load(root / config['planning_source'])
                self.assertEqual([j['date'] for j in jobs], [f'2026-11-{d:02}' for d in range(5, 16)])
                self.assertTrue(all(j['channel_id'] == latest.CHANNEL and j['publish_local'].endswith('T13:00:00+08:00') for j in jobs))
                manifest = run.load(root / config['assets_path'] / 'manifest.json')
                self.assertEqual(manifest['titles_per_job'], 1)
                for entry in manifest['jobs']:
                    creative = run.load(root / config['work'] / entry['job_id'] / 'creative.json')
                    self.assertEqual(creative['titles'], entry['titles'])
                    self.assertEqual(len(entry['titles']), 1)
                    self.assertLessEqual(len(entry['titles'][0].encode('utf-16-le')) // 2, 100)
                    cover = root / config['assets_path'] / entry['covers'][0]
                    self.assertLess(cover.stat().st_size, 2000000)
                    with Image.open(cover) as image:
                        self.assertEqual(image.size, (1920, 1080))
                self.assertEqual(latest.prepare_latest(), path)
                self.assertIn(str(path.resolve()), available_profiles(path).values())
                custom = root / 'custom-en2'
                shutil.copytree(root / latest.PACK, custom)
                set_material_folder('en2', custom)
                shutil.rmtree(root / latest.PACK)
                self.assertEqual(latest.prepare_latest(), path)
                settings = run.load(root / SETTINGS)
                self.assertEqual(settings['en2'], str(custom.resolve()))
                self.assertEqual(settings['en'], 'english-one-untouched')
                self.assertEqual(settings['tl'], 'filipino-untouched')
                self.assertEqual(run.load(receipt), {'keep': True})

    def test_clean_install_binds_correct_channel_and_separate_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO / latest.PACK, root / latest.PACK)
            with patch.object(run, 'ROOT', root), patch.object(run, 'auth', side_effect=AssertionError('offline only')), contextlib.redirect_stdout(io.StringIO()):
                path = latest.prepare_latest()
                config = run.load(path)
                self.assertEqual(config['channel_id'], latest.CHANNEL)
                self.assertEqual(config['material_key'], 'en2')
                self.assertIn(latest.CHANNEL, config['oauth_token'])
                self.assertEqual(config['http_timeout_seconds'], 120)

    def test_legacy_runtime_rejected_with_upgrade_instruction(self):
        with patch.object(run, 'SUPPORTED_TITLE_COUNTS', (3,)):
            with self.assertRaisesRegex(ValueError, '旧版run.py'):
                latest.prepare_latest()


if __name__ == '__main__':
    unittest.main()
