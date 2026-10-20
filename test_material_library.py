import contextlib
import copy
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
import run
from material_library import load_materials,set_material_folder,material_folder,find_pack

class MaterialLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.patch=patch.object(run,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.config={'channel_id':'UC'+'a'*22,'channel_name':'韩语','language':'ko','assets_path':'unused','work':'old_work','planning_source':'obsolete.json','start_date':'2099-01-01','oauth_token':'token.ko.json','proxy_url':''}
        self.folder=self.root/'韩语';self.folder.mkdir();set_material_folder('ko',self.folder)
        self.pack=self.folder/'batch';self.pack.mkdir()
        self.write_pack()
    def write_pack(self,title='剧一'):
        image=self.pack/'cover.jpg';Image.new('RGB',(1280,720),'navy').save(image)
        self.manifest={'language':'ko','jobs':[{'job_id':'one','title_zh':title,'date':'2026-11-01','drama_code':'ko1','titles':['가','나','다'],'covers':['cover.jpg']}],'sha256':{'cover.jpg':run.digest(image)}}
        self.jobs=[{'job_id':'one','title_zh':title,'date':'2026-11-01','language':'ko','timezone':'Asia/Shanghai','publish_local':'2026-11-01T17:00:00+08:00','publish_at':'2026-11-01T09:00:00Z','candidates':[{'drama_code':'ko1','audio_language':'ko'}],'blockers':[]}]
        self.save_pack()
    def save_pack(self):
        run.save(self.pack/'manifest.json',self.manifest);run.save(self.pack/'schedule.json',self.jobs)
    def load(self):
        with contextlib.redirect_stdout(io.StringIO()):return load_materials(self.config)
    def test_replace_package_without_editing_config_and_keep_old_batch(self):
        old=self.load();c=run.load(old)
        self.assertEqual(run.load(self.root/c['work']/'queue.json')[0]['title_zh'],'剧一')
        self.assertNotIn('start_date',c)
        self.assertEqual(self.config['planning_source'],'obsolete.json')
        self.write_pack('剧二');new=self.load()
        self.assertNotEqual(old,new);self.assertTrue(old.exists())
        self.assertEqual(run.load(self.root/run.load(new)['work']/'queue.json')[0]['title_zh'],'剧二')
    def test_same_batch_retains_publish_record_and_survives_source_deletion(self):
        path=self.load();c=run.load(path);record=self.root/c['work']/'one/published.json';run.save(record,{'id':'video'})
        self.assertEqual(self.load(),path);self.assertEqual(run.load(record),{'id':'video'})
        import shutil
        shutil.rmtree(self.pack)
        self.assertTrue((self.root/c['work']/'one/cover_1.jpg').exists())
        with self.assertRaisesRegex(ValueError,'只有一个素材包'):self.load()
    def test_bad_replacement_does_not_change_existing_batch(self):
        old=self.load();before=old.read_bytes();self.manifest['sha256']['cover.jpg']='bad';self.save_pack()
        with self.assertRaisesRegex(ValueError,'校验'):self.load()
        self.assertEqual(old.read_bytes(),before)
    def test_reject_other_language_channel_and_schedule_mismatch(self):
        for field,value in [('language','ru'),('channel_id','UC'+'b'*22)]:
            with self.subTest(field=field):
                self.manifest[field]=value;self.save_pack()
                with self.assertRaises(ValueError):self.load()
                self.manifest.pop(field)
                self.manifest['language']='ko'
        self.jobs[0]['title_zh']='错误剧名';self.save_pack()
        with self.assertRaisesRegex(ValueError,'剧名'):self.load()
    def test_multiple_packages_and_missing_schedule_are_rejected(self):
        run.save(self.folder/'another/manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'当前找到：2'):self.load()
        import shutil
        shutil.rmtree(self.folder/'another');(self.pack/'schedule.json').unlink()
        with self.assertRaisesRegex(ValueError,'schedule.json'):self.load()
    def test_paths_are_saved_independently_for_languages_and_external_folders(self):
        other=self.root/'俄语';other.mkdir();set_material_folder('ru',other)
        self.assertEqual(material_folder(self.config),self.folder)
        self.assertEqual(material_folder(dict(self.config,language='ru')),other)
    def test_path_traversal_and_inconsistent_time_are_rejected(self):
        self.manifest['jobs'][0]['covers']=['../outside.jpg'];self.save_pack()
        with self.assertRaisesRegex(ValueError,'路径'):self.load()
        self.write_pack();self.jobs[0]['publish_at']='2026-11-01T10:00:00Z';self.save_pack()
        with self.assertRaisesRegex(ValueError,'UTC'):self.load()
    def test_import_failure_is_atomic(self):
        self.manifest['jobs'][0]['titles']=['only one'];self.save_pack()
        with self.assertRaisesRegex(ValueError,'three titles'):self.load()
        self.assertFalse(list((self.root/'local_work_materials').rglob('config.json')))
