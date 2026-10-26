import argparse
import contextlib
import datetime as dt
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
import run
from spanish_start import prepare_spanish,CHANNEL,RELEASE_STATE
from material_library import load_materials,material_folder,set_material_folder
from publisher_profiles import remember_profile
REPO=run.ROOT
PACK=REPO/'materials/西语/assets_es_20261106_two_daily'
class SpanishNovemberTests(unittest.TestCase):
    def test_first_launch_avoids_old_sibling_and_keeps_other_channel_settings(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);new=root/'materials/西语/new';old=root/'materials/西语/old'
            new.mkdir(parents=True);old.mkdir();run.save(new/'manifest.json',{'language':'es','channel_id':CHANNEL})
            run.save(old/'manifest.json',{'language':'es','channel_id':CHANNEL})
            config={'language':'es','channel_id':CHANNEL,'assets_path':'materials/西语/new','oauth_token':'default','proxy_url':'default','http_timeout_seconds':120}
            run.save(root/'profiles/spanish.json',config)
            en=root/'english';en.mkdir();set_material_folder('en',en);set_material_folder('es',old)
            previous=root/'previous.json';run.save(previous,dict(config,oauth_token='keep.es',proxy_url='',http_timeout_seconds=60));remember_profile(previous)
            active=root/'active.json';run.save(active,config)
            with patch('spanish_start.load_materials',return_value=active) as loader,patch.object(run,'auth') as auth:
                self.assertEqual(prepare_spanish(),active)
                self.assertEqual(material_folder(config),new)
                self.assertEqual(loader.call_args.args[0]['oauth_token'],'keep.es')
                self.assertEqual(loader.call_args.args[0]['proxy_url'],'')
                self.assertEqual(loader.call_args.args[0]['http_timeout_seconds'],60)
                custom=root/'custom';custom.mkdir();set_material_folder('es',custom)
                shutil.rmtree(new);prepare_spanish();self.assertEqual(material_folder(config),custom)
                auth.assert_not_called()
            self.assertEqual(run.load(root/'local_work_publisher_ui/material_folders.json')['en'],str(en))
            self.assertTrue((root/RELEASE_STATE).exists())
    def test_wrong_channel_token_is_not_reused_and_wrong_preset_stops(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);new=root/'pack';new.mkdir();run.save(new/'manifest.json',{'language':'es','channel_id':CHANNEL})
            config={'language':'es','channel_id':CHANNEL,'assets_path':'pack','oauth_token':'token.es'}
            run.save(root/'profiles/spanish.json',config)
            previous=root/'previous.json';run.save(previous,dict(config,channel_id='UC'+'a'*22,oauth_token='other'));remember_profile(previous)
            active=root/'active.json';run.save(active,config)
            with patch('spanish_start.load_materials',return_value=active) as loader:
                prepare_spanish();self.assertEqual(loader.call_args.args[0]['oauth_token'],'token.es')
            run.save(root/'profiles/spanish.json',dict(config,channel_id='UC'+'b'*22))
            with self.assertRaisesRegex(ValueError,'频道不一致'):prepare_spanish()
    def test_real_materials_times_codes_single_titles_and_immutable_import(self):
        m=run.load(PACK/'manifest.json');jobs=run.load(PACK/'schedule.json')
        self.assertEqual(len(jobs),20);self.assertEqual(len(m['jobs']),20)
        self.assertEqual(jobs[0]['date'],'2026-11-06');self.assertEqual(jobs[-1]['date'],'2026-11-15')
        self.assertEqual(m['titles_per_job'],1)
        schedule=run.load(REPO/'schedules/spanish_20261106_20261115_two_daily/schedule.json')['rows']
        for i,(job,entry,row) in enumerate(zip(jobs,m['jobs'],schedule)):
            self.assertEqual(job['title_zh'],row['剧名']);self.assertEqual(entry['drama_code'],row['剧集代码'])
            self.assertEqual(job['publish_local'],row['publish_local']);self.assertEqual(job['channel_id'],CHANNEL)
            self.assertEqual(job['publish_local'][11:16],('00:00','05:00')[i%2])
            self.assertEqual(dt.datetime.fromisoformat(job['publish_local']),dt.datetime.fromisoformat(job['publish_at'].replace('Z','+00:00')))
            self.assertEqual(len(entry['titles']),1);self.assertLessEqual(len(entry['titles'][0].encode('utf-16-le'))//2,100)
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);config=run.load(REPO/'profiles/spanish.json');set_material_folder('es',PACK)
            with patch.object(run,'auth',side_effect=AssertionError('offline only')):
                path=load_materials(config);active=run.load(path);self.assertEqual(load_materials(active),path)
                for e in m['jobs']:
                    image=root/active['work']/e['job_id']/'cover_1.jpg'
                    self.assertEqual(run.digest(image),m['sha256'][e['covers'][0]])
                    with Image.open(image) as im:self.assertEqual(im.size,(1920,1080))
                    self.assertLess(image.stat().st_size,2*1024*1024)
                with self.assertRaisesRegex(ValueError,'其他频道'):load_materials(dict(config,channel_id='UC'+'z'*22))
            job=jobs[0];entry=m['jobs'][0];api=Mock();original='Descripción original.  \r\n#drama\r\n'
            video={'id':'video000001','etag':'v1','snippet':{'channelId':CHANNEL,'title':job['title_zh'],'description':original,'categoryId':'24'},'status':{'privacyStatus':'private','uploadStatus':'processed'}}
            api.videos.return_value.list.return_value.execute.return_value={'items':[video]}
            when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None,microsecond=0).isoformat()
            with patch.object(run,'auth',return_value=api):run.review(active,argparse.Namespace(job=job['job_id'],video_id=video['id'],code=None,title=1,cover=1,publish_local=when))
            review=run.load(root/active['work']/job['job_id']/'review.json');self.assertEqual(review['title'],entry['titles'][0]);self.assertEqual(review['description_after'],original+entry['drama_code'])
            api.videos.return_value.update.assert_not_called()
