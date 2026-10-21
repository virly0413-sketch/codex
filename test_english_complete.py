import argparse
import contextlib
import datetime as dt
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from PIL import Image
import run
from english_start import prepare_english, CHANNEL, RELEASE_STATE
from material_library import load_materials, material_folder, set_material_folder

REPO=run.ROOT
PACK=REPO/'materials/英语/assets_en_20261026_action_v2'


class EnglishCompleteTests(unittest.TestCase):
    def test_first_release_replaces_stale_folder_then_respects_custom_folder_and_preferences(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);bundled=root/'materials/英语/new';bundled.mkdir(parents=True)
            run.save(bundled/'manifest.json',{'language':'en','channel_id':CHANNEL,'release':'new'})
            config={'language':'en','channel_id':CHANNEL,'assets_path':'materials/英语/new','oauth_token':'new-token-path','proxy_url':'default'}
            run.save(root/'profiles/english.json',config)
            old=root/'old';old.mkdir();set_material_folder('en',old)
            previous=root/'previous.json';run.save(previous,dict(config,proxy_url='',http_timeout_seconds=60,oauth_token='keep-token-path'))
            active=root/'active.json';run.save(active,config)
            with patch('english_start.initial_profile',return_value=previous),patch('english_start.load_materials',return_value=active) as loader,patch.object(run,'auth') as auth:
                self.assertEqual(prepare_english(),active)
                self.assertEqual(material_folder(config),bundled.parent)
                self.assertEqual(loader.call_args.args[0]['oauth_token'],'keep-token-path')
                self.assertEqual(loader.call_args.args[0]['proxy_url'],'')
                self.assertEqual(loader.call_args.args[0]['http_timeout_seconds'],60)
                custom=root/'custom';custom.mkdir();set_material_folder('en',custom)
                self.assertEqual(prepare_english(),active)
                self.assertEqual(material_folder(config),custom)
                # Future packs may have a new folder name; the original shipped pack can be removed.
                (bundled/'manifest.json').unlink();bundled.rmdir()
                self.assertEqual(prepare_english(),active)
                self.assertEqual(material_folder(config),custom)
                auth.assert_not_called()
            self.assertTrue((root/RELEASE_STATE).is_file())

    def test_other_channel_preferences_are_not_reused_and_wrong_preset_stops(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)):
            root=Path(tmp);p=root/'materials/英语/new';p.mkdir(parents=True)
            run.save(p/'manifest.json',{'language':'en','channel_id':CHANNEL})
            config={'language':'en','channel_id':CHANNEL,'assets_path':'materials/英语/new','oauth_token':'english-token'}
            run.save(root/'profiles/english.json',config)
            previous=root/'previous.json';run.save(previous,{'language':'es','channel_id':'UC'+'s'*22,'oauth_token':'spanish-token'})
            active=root/'active.json';run.save(active,config)
            with patch('english_start.initial_profile',return_value=previous),patch('english_start.load_materials',return_value=active) as loader:
                prepare_english();self.assertEqual(loader.call_args.args[0]['oauth_token'],'english-token')
            run.save(root/'profiles/english.json',dict(config,channel_id='UC'+'x'*22))
            with self.assertRaisesRegex(ValueError,'频道不一致'):prepare_english()

    def test_real42_job_pack_preserves_pixels_and_description_and_rejects_wrong_channel(self):
        m=run.load(PACK/'manifest.json');jobs=run.load(PACK/'schedule.json')
        self.assertEqual(len(jobs),42);self.assertEqual(len(m['jobs']),42)
        self.assertEqual(jobs[0]['date'],'2026-10-26');self.assertEqual(jobs[-1]['date'],'2026-11-15')
        self.assertEqual(len({t for e in m['jobs'] for t in e['titles']}),126)
        self.assertEqual(m['thumbnail_resolution'],[1920,1080])
        old=run.load(REPO/'assets_en_20261026_1080p/manifest.json')
        self.assertTrue(set(m['sha256'].values()).isdisjoint(old['sha256'].values()))
        old_titles={t for e in old['jobs'] for t in e['titles']}
        self.assertTrue(old_titles.isdisjoint(t for e in m['jobs'] for t in e['titles']))
        for j in jobs:
            self.assertIn(j['publish_local'][11:16],['17:00','21:00'])
            self.assertEqual(j['channel_id'],CHANNEL)
        for e in m['jobs']:
            for t in e['titles']:self.assertLessEqual(len(t.encode('utf-16-le'))//2,100)
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);config=run.load(REPO/'profiles/english.json');set_material_folder('en',PACK)
            with patch.object(run,'auth',side_effect=AssertionError('offline only')):
                path=load_materials(config);active=run.load(path);self.assertEqual(load_materials(active),path)
                for e in m['jobs']:
                    image=root/active['work']/e['job_id']/'cover_1.jpg'
                    self.assertEqual(run.digest(image),m['sha256'][e['covers'][0]])
                    with Image.open(image) as im:self.assertEqual(im.size,(1920,1080))
                with self.assertRaisesRegex(ValueError,'其他频道'):load_materials(dict(config,channel_id='UC'+'z'*22))
            j=jobs[0];e=m['jobs'][0];api=Mock()
            video={'id':'video000001','etag':'v1','snippet':{'channelId':CHANNEL,'title':j['title_zh'],
                  'description':'Original description.  \r\n#drama\r\n','categoryId':'24'},
                  'status':{'privacyStatus':'private','uploadStatus':'processed'}}
            api.videos.return_value.list.return_value.execute.return_value={'items':[video]}
            when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None,microsecond=0).isoformat()
            with patch.object(run,'auth',return_value=api):
                run.review(active,argparse.Namespace(job=j['job_id'],video_id=video['id'],code=None,title=1,cover=1,publish_local=when))
            review=run.load(root/active['work']/j['job_id']/'review.json')
            self.assertEqual(review['title'],e['titles'][0])
            self.assertEqual(review['description_after'],video['snippet']['description']+e['drama_code'])
            api.videos.return_value.update.assert_not_called();api.thumbnails.return_value.set.assert_not_called()


if __name__=='__main__':unittest.main()
