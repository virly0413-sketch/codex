import argparse
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import run

class FourKImportTests(unittest.TestCase):
    def check_import(self,size,oversized=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pack=root/'pack';pack.mkdir()
            source=pack/'cover.jpg';Image.new('RGB',size,'navy').save(source)
            if oversized:
                with source.open('ab') as f:f.write(b' '*(2*1024*1024))
            job={'job_id':'one','title_zh':'test','candidates':[{'drama_code':'code'}]}
            run.save(root/'work/queue.json',[job])
            run.save(pack/'manifest.json',{'preserve_thumbnail_resolution':True,'sha256':{'cover.jpg':run.digest(source)},'jobs':[{'job_id':'one','title_zh':'test','drama_code':'code','titles':['a','b','c'],'covers':['cover.jpg']}]})
            with patch.object(run,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):
                config={'work':'work','channel_id':'UC'+'a'*22}
                args=argparse.Namespace(pack=str(pack))
                if size!=(3840,2160) or oversized:
                    with self.assertRaisesRegex(ValueError,'4K素材'):run.import_pack(config,args)
                    self.assertFalse((root/'work/one/creative.json').exists())
                else:
                    run.import_pack(config,args)
                    target=root/'work/one/cover_1.jpg'
                    self.assertEqual(target.read_bytes(),source.read_bytes())
                    with Image.open(target) as im:self.assertEqual(im.size,(3840,2160))
    def test_4k_preserves_resolution_and_bytes(self):self.check_import((3840,2160))
    def test_wrong_resolution_is_rejected(self):self.check_import((1280,720))
    def test_oversized_4k_is_rejected(self):self.check_import((3840,2160),True)

    def test_explicit_1080p_import_preserves_bytes_and_rejects_other_sizes(self):
        for size in ((1920,1080),(1280,720),(3840,2160)):
            with self.subTest(size=size),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);pack=root/'pack';pack.mkdir()
                source=pack/'cover.jpg';Image.new('RGB',size,'navy').save(source)
                run.save(root/'work/queue.json',[{'job_id':'one','title_zh':'test','candidates':[{'drama_code':'code'}]}])
                run.save(pack/'manifest.json',{
                    'preserve_thumbnail_resolution':True,'thumbnail_resolution':[1920,1080],
                    'sha256':{'cover.jpg':run.digest(source)},
                    'jobs':[{'job_id':'one','title_zh':'test','drama_code':'code',
                             'titles':['a','b','c'],'covers':['cover.jpg']}]})
                with patch.object(run,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):
                    config={'work':'work','channel_id':'UC'+'a'*22}
                    if size==(1920,1080):
                        run.import_pack(config,argparse.Namespace(pack=str(pack)))
                        self.assertEqual((root/'work/one/cover_1.jpg').read_bytes(),source.read_bytes())
                    else:
                        with self.assertRaisesRegex(ValueError,'1080p素材'):
                            run.import_pack(config,argparse.Namespace(pack=str(pack)))
                        self.assertFalse((root/'work/one/creative.json').exists())
