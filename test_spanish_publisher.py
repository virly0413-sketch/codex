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
from desktop import App
from material_library import set_material_folder,load_materials
from publisher_profiles import available_profiles,validate_profile
REPO=run.ROOT
CHANNEL='UCaQI24vmsim_8jDI0NuwbEg'

class SpanishPublisherTests(unittest.TestCase):
    def test_spanish_preset_isolated_and_ui_switch_only_loads_offline(self):
        choices=available_profiles();name=next(n for n in choices if n.startswith('西语'))
        config=validate_profile(choices[name]);self.assertEqual(config['channel_id'],CHANNEL)
        self.assertEqual(config['language'],'es');self.assertIn('token.es.',config['oauth_token'])
        app=App.__new__(App);app.busy=False;app.profile_paths=choices;app.profile_name=Mock();app.profile_name.get.return_value=name
        app.activate_profile=Mock();app.task=lambda fn,after:(fn(),after())
        with patch('desktop.load_materials',return_value=Path(choices[name])) as loader,patch.object(run,'auth') as auth:
            app.switch_preset()
        self.assertEqual(loader.call_args.args[0]['language'],'es');auth.assert_not_called();app.activate_profile.assert_called_once()
    def test_real_21_job_pack_loads_4k_and_emoji_titles_preserve_description(self):
        config=dict(run.load(REPO/'profiles/spanish.json'),assets_path='assets_es_20261026',planning_source='data/jobs.es.20261026.json');pack=REPO/config['assets_path'];manifest=run.load(pack/'manifest.json')
        jobs=run.load(pack/'schedule.json')
        self.assertEqual(len(jobs),21);self.assertEqual(jobs[0]['date'],'2026-10-26');self.assertEqual(jobs[-1]['date'],'2026-11-15')
        self.assertEqual({j['language'] for j in jobs},{'es'})
        for entry in manifest['jobs']:
            self.assertEqual(len(entry['titles']),3)
            for title in entry['titles']:
                self.assertLessEqual(len(title.encode('utf-16-le'))//2,100)
                self.assertTrue(any(ord(ch)>0x2600 for ch in title))
                self.assertNotRegex(title,r'[\uac00-\ud7af]')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(run,'ROOT',root),contextlib.redirect_stdout(io.StringIO()),patch.object(run,'auth',side_effect=AssertionError('offline import')):
                set_material_folder('es',pack);path=load_materials(config)
                active=run.load(path);queue=run.load(root/active['work']/'queue.json')
                self.assertEqual(len(queue),21);self.assertEqual(load_materials(active),path)
                for j in queue:
                    with Image.open(root/active['work']/j['job_id']/'cover_1.jpg') as im:self.assertEqual(im.size,(3840,2160))
                with self.assertRaisesRegex(ValueError,'其他频道'):
                    load_materials(dict(config,channel_id='UC'+'a'*22))
            job=queue[0];entry=manifest['jobs'][0];api=Mock()
            api.videos.return_value.list.return_value.execute.return_value={'items':[{'id':'video000001','etag':'v1','snippet':{'channelId':CHANNEL,'title':job['title_zh'],'description':'Descripción ya existente.  \n#drama\n','categoryId':'24','defaultAudioLanguage':'es'},'status':{'privacyStatus':'private','uploadStatus':'processed'}}]}
            when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None,microsecond=0).isoformat()
            with patch.object(run,'ROOT',root),patch.object(run,'auth',return_value=api),contextlib.redirect_stdout(io.StringIO()):
                run.review(active,argparse.Namespace(job=job['job_id'],video_id='video000001',code=entry['drama_code'],title=1,cover=1,publish_local=when))
            review=run.load(root/active['work']/job['job_id']/'review.json')
            self.assertEqual(review['title'],entry['titles'][0])
            self.assertEqual(review['description_after'],'Descripción ya existente.  \n#drama\n'+entry['drama_code'])
            api.videos.return_value.update.assert_not_called();api.thumbnails.return_value.set.assert_not_called()
