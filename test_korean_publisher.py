import argparse
import contextlib
import datetime as dt
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import run
from korean_start import korean_config

REPO=run.ROOT

class KoreanPublisherTests(unittest.TestCase):
    def test_channel_configuration_is_separate_and_requires_uc_id(self):
        with self.assertRaises(ValueError):korean_config('@handle')
        first=korean_config('UC'+'a'*22);second=korean_config('UC'+'b'*22)
        self.assertEqual(first['language'],'ko')
        self.assertNotEqual(first['work'],second['work'])
        self.assertNotEqual(first['oauth_token'],second['oauth_token'])
        self.assertNotIn(first['work'],('local_work','local_work_ru_20261020'))
    def test_real_asset_import_and_review_use_korean_title_and_append_only_code(self):
        config=korean_config('UCYIkDEkNEAiaJA2HkBZtNFA')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            (root/config['planning_source']).write_bytes((REPO/config['planning_source']).read_bytes())
            with patch.object(run,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):
                run.plan(config)
                args=argparse.Namespace(pack=str(REPO/config['assets_path']))
                run.import_pack(config,args)
                queue=run.load(root/config['work']/'queue.json')
                self.assertEqual(len(queue),21)
                self.assertEqual(queue[0]['date'],'2026-10-26')
                self.assertEqual(queue[-1]['date'],'2026-11-15')
                for job in queue:
                    creative=run.load(root/config['work']/job['job_id']/'creative.json')
                    self.assertEqual(creative['language'],'ko')
                    self.assertEqual(creative['drama_code'],job['candidates'][0]['drama_code'])
                    self.assertEqual(creative['cover_count'],1)
                run.import_pack(config,args)  # Idempotent re-import must preserve existing creatives.
                j=queue[0];creative=run.load(root/config['work']/j['job_id']/'creative.json')
                api=Mock()
                api.videos.return_value.list.return_value.execute.return_value={'items':[{
                    'id':'video000001','etag':'v1','snippet':{'channelId':config['channel_id'],
                    'title':j['title_zh'],'description':'已有说明保持原样  \n#tag\n','categoryId':'24','defaultAudioLanguage':'ko'},
                    'status':{'privacyStatus':'private','uploadStatus':'processed'}}]}
                when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).astimezone(dt.timezone(dt.timedelta(hours=8))).replace(tzinfo=None,microsecond=0).isoformat()
                with patch.object(run,'auth',return_value=api):
                    run.review(config,argparse.Namespace(job=j['job_id'],video_id='video000001',code=creative['drama_code'],title=1,cover=1,publish_local=when))
                review=run.load(root/config['work']/j['job_id']/'review.json')
                self.assertEqual(review['title'],creative['titles'][0])
                self.assertEqual(review['description_after'],'已有说明保持原样  \n#tag\n'+creative['drama_code'])
                api.videos.return_value.update.assert_not_called()
                api.thumbnails.return_value.set.assert_not_called()
                with self.assertRaisesRegex(ValueError,'语种'):
                    run.import_pack(dict(config,language='ru'),args)
