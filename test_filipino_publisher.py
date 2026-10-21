import argparse
import contextlib
import datetime as dt
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
import run
from filipino_setup import bind_channel, ensure_profile, valid_channel
from material_library import load_materials, set_material_folder
from publisher_profiles import available_profiles
import publisher_start

REPO=run.ROOT
PACK=REPO/'materials/菲律宾语/assets_tl_20261026_ready'
CHANNEL='UC'+'t'*22  # Fixture only, never a shipped or real channel binding.


class FilipinoTests(unittest.TestCase):
    def test_channel_binding_rejects_handle_and_preserves_other_profiles(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)):
            for invalid in ('', '@channel', 'UCshort', 'https://youtube.com/channel/'+CHANNEL):
                self.assertFalse(valid_channel(invalid))
                with self.assertRaises(ValueError):bind_channel(invalid)
            other=Path(tmp)/'profiles/english.json';run.save(other,{'keep':True})
            path=bind_channel(CHANNEL);config=run.load(path)
            self.assertEqual(config['language'],'tl');self.assertIn(CHANNEL,config['oauth_token'])
            config['proxy_url']='';run.save(path,config)
            self.assertEqual(run.load(bind_channel(CHANNEL))['proxy_url'],'')
            self.assertEqual(run.load(other),{'keep':True})
            config2=run.load(bind_channel('UC'+'u'*22))
            self.assertNotEqual(config['oauth_token'],config2['oauth_token'])
            self.assertNotEqual(config['work'],config2['work'])

    def test_first_use_cancel_does_not_create_profile_or_call_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),\
             patch('tkinter.simpledialog.askstring',return_value=None),patch.object(run,'auth') as auth:
            self.assertIsNone(ensure_profile(Mock()))
            self.assertFalse((Path(tmp)/'profiles/filipino.json').exists());auth.assert_not_called()

    def test_registered_profile_appears_in_switcher_without_prompt(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)):
            path=bind_channel(CHANNEL)
            choices=available_profiles()
            self.assertEqual(choices,{'菲律宾语 | 菲律宾语男频':str(path.resolve())})
            with patch('tkinter.simpledialog.askstring',side_effect=AssertionError('must not ask again')):
                self.assertEqual(ensure_profile(Mock()),path)

    def test_launcher_cancel_and_saved_preferences_are_respected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)):
            root=Path(tmp);path=bind_channel(CHANNEL)
            active=dict(run.load(path),proxy_url='',http_timeout_seconds=60)
            saved=root/'batch/config.json';run.save(saved,active)
            window=Mock()
            with patch('publisher_start.tk.Tk',return_value=window),\
                 patch('filipino_setup.ensure_profile',return_value=None),\
                 patch('publisher_start.App') as app,patch('material_library.load_materials') as loader:
                publisher_start.start(filipino=True)
            app.assert_not_called();loader.assert_not_called();window.destroy.assert_called_once()
            window=Mock()
            with patch('publisher_start.tk.Tk',return_value=window),\
                 patch('publisher_start.initial_profile',return_value=saved),\
                 patch('filipino_setup.ensure_profile',return_value=path),\
                 patch('publisher_start.App') as app,\
                 patch('material_library.load_materials',return_value=saved) as loader:
                publisher_start.start(filipino=True)
            self.assertEqual(loader.call_args.args[0]['proxy_url'],'')
            self.assertEqual(loader.call_args.args[0]['http_timeout_seconds'],60)
            app.assert_called_once_with(window,saved);window.mainloop.assert_called_once()

    def test_real_complete_pack_import_idempotency_channel_isolation_and_description(self):
        manifest=run.load(PACK/'manifest.json');jobs=run.load(PACK/'schedule.json')
        self.assertEqual(len(jobs),21);self.assertEqual(jobs[0]['date'],'2026-10-26')
        self.assertEqual(jobs[-1]['date'],'2026-11-15')
        for j,e in zip(jobs,manifest['jobs']):
            self.assertEqual(j['publish_local'],j['date']+'T17:00:00+08:00')
            self.assertEqual(len(e['titles']),3)
            self.assertTrue(all(len(t.encode('utf-16-le'))//2<=100 for t in e['titles']))
            self.assertEqual(e['language'],'tl');self.assertEqual(e['drama_code'],j['candidates'][0]['drama_code'])
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);config=run.load(bind_channel(CHANNEL))
            set_material_folder('tl',PACK)
            with patch.object(run,'auth',side_effect=AssertionError('offline only')):
                path=load_materials(config);active=run.load(path)
                self.assertEqual(load_materials(active),path)
                for entry in manifest['jobs']:
                    image=root/active['work']/entry['job_id']/'cover_1.jpg'
                    with Image.open(image) as im:self.assertEqual(im.size,(1920,1080))
                    self.assertEqual(run.digest(image),manifest['sha256'][entry['covers'][0]])
                with self.assertRaisesRegex(ValueError,'语种'):
                    load_materials(dict(config,language='ru',assets_path=str(PACK)))
            entry=manifest['jobs'][0];j=jobs[0];api=Mock()
            video={'id':'video000001','etag':'v1','snippet':{'channelId':CHANNEL,'title':j['title_zh'],
                'description':'Orihinal na paglalarawan.  \r\n#drama\r\n','categoryId':'24'},
                'status':{'privacyStatus':'private','uploadStatus':'processed'}}
            api.videos.return_value.list.return_value.execute.return_value={'items':[video]}
            when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None,microsecond=0).isoformat()
            with patch.object(run,'auth',return_value=api):
                run.review(active,argparse.Namespace(job=j['job_id'],video_id=video['id'],code=None,title=1,cover=1,publish_local=when))
            review=run.load(root/active['work']/j['job_id']/'review.json')
            self.assertEqual(review['description_after'],video['snippet']['description']+entry['drama_code'])
            self.assertEqual(review['title'],entry['titles'][0])
            api.videos.return_value.update.assert_not_called();api.thumbnails.return_value.set.assert_not_called()


if __name__=='__main__':unittest.main()
