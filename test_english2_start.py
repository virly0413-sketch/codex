import argparse
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import run
import english2_start
from desktop import App
from material_library import material_folder,set_material_folder
from publisher_profiles import remember_profile

REPO=run.ROOT
class English2Tests(unittest.TestCase):
    def test_channel_materials_startup_and_folder_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('profiles/english2.json','data/jobs.en2.current.json'):
                (root/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(REPO/name,root/name)
            pack='materials/英语2/assets_en2_current_14'
            shutil.copytree(REPO/pack,root/pack)
            with patch.object(run,'ROOT',root),patch.object(run,'auth') as auth,contextlib.redirect_stdout(io.StringIO()):
                original=root/'original';original.mkdir();set_material_folder('en',original)
                old=dict(run.load(root/'profiles/english2.json'),channel_id='UC'+'a'*22,oauth_token='wrong.json')
                run.save(root/'old.json',old);remember_profile(root/'old.json')
                path=english2_start.prepare_english2();config=run.load(path)
                self.assertNotEqual(config['oauth_token'],'wrong.json')
                self.assertEqual(run.load(root/'local_work_publisher_ui/material_folders.json')['en'],str(original))
                queue=run.load(root/config['work']/'queue.json');self.assertEqual(len(queue),14)
                self.assertEqual(sum(j['publish_local'] is None for j in queue),0)
                for job in queue:
                    self.assertTrue(job['publish_local'].endswith('T13:00:00+08:00'))
                    self.assertTrue(job['publish_at'].endswith('T05:00:00Z'))
                self.assertEqual(queue[-1]['date'],'2026-11-06')
                manifest=run.load(root/pack/'manifest.json')
                for job,entry in zip(queue,manifest['jobs']):
                    directory=root/config['work']/job['job_id']
                    self.assertEqual(len(run.load(directory/'creative.json')['titles']),1)
                    self.assertEqual(run.digest(directory/'cover_1.jpg'),manifest['sha256'][entry['covers'][0]])
                self.assertEqual(english2_start.prepare_english2(),path)
                # A subsequent source replacement respects the custom English2 folder.
                custom=root/'custom';custom.mkdir();shutil.move(root/pack,custom/'renamed')
                set_material_folder('en2',custom)
                config['proxy_url']='';config['oauth_token']='own.en2.json';run.save(path,config)
                self.assertEqual(english2_start.prepare_english2(),path)
                self.assertEqual(run.load(path)['oauth_token'],'own.en2.json')
                self.assertEqual(material_folder(config),custom)
                # A complete supplied time remains usable and preserves the original description.
                job=queue[0];video={'id':'abcdefghijk','etag':'x','snippet':{'channelId':english2_start.CHANNEL,'title':job['title_zh'],'description':'Original description'},'status':{'privacyStatus':'private','uploadStatus':'processed'}}
                args=argparse.Namespace(job=job['job_id'],publish_local='2099-11-01T17:00:00',title=1,cover=1,code=None,video_id='abcdefghijk')
                with patch.object(run,'get_video',return_value=video):run.review(config,args)
                review=run.load(root/config['work']/job['job_id']/'review.json')
                self.assertEqual(review['description_after'],'Original description\n'+job['candidates'][0]['drama_code'])
                self.assertEqual(review['publish_at'],'2099-11-01T09:00:00Z')
    def test_ui_sets_channel_key_instead_of_shared_language(self):
        app=App.__new__(App);app.busy=False;app.profile_paths={'English2':REPO/'profiles/english2.json'}
        app.profile_name=Mock();app.profile_name.get.return_value='English2';app.material_info=Mock()
        with patch('desktop.filedialog.askdirectory',return_value='D:/English2'),patch('desktop.set_material_folder') as setter:
            app.configure_material_folder()
        setter.assert_called_once_with('en2','D:/English2')
