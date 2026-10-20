import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import run
from desktop import App
from publisher_profiles import available_profiles, validate_profile, remember_profile, initial_profile

REPO=run.ROOT
class PresetTests(unittest.TestCase):
    def test_same_channel_with_stale_assets_uses_updated_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.json'
            old=run.load(REPO/'profiles/korean.json')
            old['assets_path']='old_korean_assets'
            run.save(path,old)
            choices=available_profiles(path)
            selected=next(p for n,p in choices.items() if n.startswith('韩语'))
            self.assertEqual(Path(selected),REPO/'profiles/korean.json')
    def test_known_channel_and_asset_pairs_validate_including_legacy_english(self):
        choices=available_profiles()
        self.assertEqual(len(choices),4)
        configs=[validate_profile(p) for p in choices.values()]
        self.assertEqual({c['language'] for c in configs},{'en','ru','ko','es'})
        self.assertEqual(len({c['work'] for c in configs}),4)
        self.assertEqual(len({c['oauth_token'] for c in configs}),4)
    def test_switch_uses_target_config_offline_and_does_not_authorize(self):
        app=App.__new__(App);app.busy=False
        choices=available_profiles();name=next(n for n in choices if n.startswith('韩语'))
        app.profile_paths=choices;app.profile_name=Mock();app.profile_name.get.return_value=name
        app.activate_profile=Mock()
        def immediate(fn,after):fn();after()
        app.task=immediate
        with patch('desktop.load_materials',return_value=Path(choices[name])) as loader,patch.object(run,'auth') as auth:
            app.switch_preset()
        self.assertEqual(loader.call_args.args[0]['language'],'ko')
        self.assertEqual(loader.call_args.args[0]['channel_id'],'UCYIkDEkNEAiaJA2HkBZtNFA')
        auth.assert_not_called();app.activate_profile.assert_called_once()
    def test_switch_blocked_while_publishing(self):
        app=App.__new__(App);app.busy=True;app.task=Mock()
        app.switch_preset();app.task.assert_not_called()
    def test_local_last_choice_stays_within_program_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'profiles').mkdir();config=root/'profiles/korean.json';config.write_text('{}')
            with patch.object(run,'ROOT',root):
                remember_profile(config);self.assertEqual(initial_profile(),config)
                run.save(root/'local_work_publisher_ui/last_profile.json',{'config':'../../etc/passwd'})
                self.assertEqual(initial_profile(),root/'config.json')
