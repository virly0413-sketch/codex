import argparse
import contextlib
import datetime as dt
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
import run
from material_library import set_material_folder,load_materials
REPO=run.ROOT
PACK=REPO/'materials/英语/assets_en_20261101_action_v3'
CHANNEL='UC0koaDPTujsoVj-Tw27J0Qg'
class EnglishNovemberTests(unittest.TestCase):
    def test_exact_original_schedule_single_emoji_titles_and_new_images(self):
        m=run.load(PACK/'manifest.json');jobs=run.load(PACK/'schedule.json')
        originals=[j for j in run.load(REPO/'data/jobs.en.20261026.json') if j['date']>='2026-11-01']
        self.assertEqual(len(jobs),30);self.assertEqual(len(m['jobs']),30);self.assertEqual(m['titles_per_job'],1)
        old=run.load(REPO/'materials/英语/assets_en_20261026_action_v2/manifest.json')
        self.assertTrue(set(old['sha256'].values()).isdisjoint(m['sha256'].values()))
        self.assertEqual(jobs[0]['date'],'2026-11-01');self.assertEqual(jobs[-1]['date'],'2026-11-15')
        for i,(j,e,o) in enumerate(zip(jobs,m['jobs'],originals)):
            for k in ('job_id','title_zh','date','publish_local','publish_at'):self.assertEqual(j[k],o[k])
            self.assertEqual(e['drama_code'],o['candidates'][0]['drama_code'])
            self.assertEqual(j['channel_id'],CHANNEL);self.assertEqual(j['language'],'en')
            self.assertEqual(j['publish_local'][11:16],('17:00','21:00')[i%2])
            self.assertEqual(dt.datetime.fromisoformat(j['publish_local']),dt.datetime.fromisoformat(j['publish_at'].replace('Z','+00:00')))
            self.assertEqual(len(e['titles']),1);t=e['titles'][0];self.assertLessEqual(len(t.encode('utf-16-le'))//2,100)
            self.assertGreater(ord(t[0]),0x2000);self.assertGreater(ord(t.rstrip('\ufe0f')[-1]),0x2000)
    def test_offline_import_retains_bytes_description_and_separate_english2_folder(self):
        m=run.load(PACK/'manifest.json');jobs=run.load(PACK/'schedule.json')
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'ROOT',Path(tmp)),contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);config=run.load(REPO/'profiles/english.json');set_material_folder('en',PACK)
            en2=root/'english2';en2.mkdir();set_material_folder('en2',en2)
            with patch.object(run,'auth',side_effect=AssertionError('offline only')):
                path=load_materials(config);active=run.load(path);self.assertEqual(load_materials(active),path)
                for e in m['jobs']:
                    image=root/active['work']/e['job_id']/'cover_1.jpg'
                    self.assertEqual(run.digest(image),m['sha256'][e['covers'][0]])
                    with Image.open(image) as im:self.assertEqual(im.size,(1920,1080))
                    self.assertLess(image.stat().st_size,2*1024*1024)
                self.assertEqual(run.load(root/'local_work_publisher_ui/material_folders.json')['en2'],str(en2))
                with self.assertRaisesRegex(ValueError,'其他频道'):load_materials(dict(config,channel_id='UCXdinQ6fQ8RyenilKIymAFA'))
            j=jobs[0];e=m['jobs'][0];api=Mock();original='Keep original description.  \r\n#drama\r\n'
            v={'id':'video000001','etag':'v1','snippet':{'channelId':CHANNEL,'title':j['title_zh'],'description':original,'categoryId':'24'},'status':{'privacyStatus':'private','uploadStatus':'processed'}}
            api.videos.return_value.list.return_value.execute.return_value={'items':[v]}
            when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None,microsecond=0).isoformat()
            with patch.object(run,'auth',return_value=api):run.review(active,argparse.Namespace(job=j['job_id'],video_id=v['id'],code=None,title=1,cover=1,publish_local=when))
            review=run.load(root/active['work']/j['job_id']/'review.json');self.assertEqual(review['title'],e['titles'][0]);self.assertEqual(review['description_after'],original+e['drama_code'])
            api.videos.return_value.update.assert_not_called();api.thumbnails.return_value.set.assert_not_called()
