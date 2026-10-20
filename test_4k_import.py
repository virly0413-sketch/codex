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
