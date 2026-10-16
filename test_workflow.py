import datetime as dt
import tempfile
import unittest
from pathlib import Path

from prepare import prepare, description_with_code
from run import fingerprint, save, load, approve
from types import SimpleNamespace
import run
from unittest.mock import MagicMock, patch


class WorkflowTests(unittest.TestCase):
    def test_description_preservation_and_idempotence(self):
        for text in ['', 'Text  ', 'Text\r\n\r\n', '#tag\nlink']:
            updated = description_with_code(text, '2609 KR80')
            self.assertTrue(updated.startswith(text))
            self.assertEqual(updated.splitlines()[-1], '2609 KR80')
            self.assertEqual(description_with_code(updated, '2609 KR80'), updated)
        with self.assertRaises(ValueError):
            description_with_code('a', 'code\nmore')

    def test_bundled_schedule_and_assets(self):
        root = Path(__file__).parent
        q = load(root / 'data/jobs.json')
        assets = load(root / 'assets/manifest.json')['jobs']
        self.assertEqual(len(q), 8)
        self.assertEqual({j['job_id'] for j in q}, {j['job_id'] for j in assets})
        self.assertEqual(min(j['date'] for j in q), '2026-10-22')
        self.assertEqual(max(j['date'] for j in q), '2026-10-25')
        first = [j for j in q if j['date'] == '2026-10-22']
        self.assertEqual([j['publish_at'] for j in first],
                         ['2026-10-22T09:00:00Z', '2026-10-22T13:00:00Z'])
        self.assertTrue(all(not j['approved'] for j in q))

    def test_approval_binds_content(self):
        self.assertNotEqual(fingerprint({'title': 'A'}), fingerprint({'title': 'B'}))
        with tempfile.TemporaryDirectory() as folder:
            original = run.ROOT
            try:
                run.ROOT = Path(folder)
                config = {'work': 'work'}
                p = run.ROOT / 'work/job/review.json'
                package = {'demo': False, 'title': 'A'}
                save(p, package)
                args = SimpleNamespace(job='job', fingerprint='wrong')
                with self.assertRaises(ValueError): approve(config, args)
                self.assertFalse((p.parent / 'approval.json').exists())
                args.fingerprint = fingerprint(package)
                approve(config, args)
                self.assertEqual(load(p.parent/'approval.json')['fingerprint'], fingerprint(package))
                package['demo'] = True
                save(p, package)
                args.fingerprint = fingerprint(package)
                with self.assertRaises(ValueError): approve(config, args)
            finally:
                run.ROOT = original

    def test_upload_private_then_schedule_and_resume_without_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            original = run.ROOT
            try:
                run.ROOT = Path(folder)
                directory = run.ROOT / 'work/job'
                directory.mkdir(parents=True)
                video, cover = directory/'video.mp4', directory/'cover.jpg'
                video.write_bytes(b'fake video for mocked transport')
                cover.write_bytes(b'fake thumbnail for mocked transport')
                when = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).replace(microsecond=0)
                package = dict(demo=False, channel_id='test-channel', title='Approved title',
                    description_after='Original\nCODE', video=str(video), thumbnail=str(cover),
                    video_sha256=run.digest(video), thumbnail_sha256=run.digest(cover),
                    publish_at=when.isoformat(), publish_local=when.isoformat())
                save(directory/'review.json', package)
                save(directory/'approval.json', {'fingerprint': fingerprint(package)})
                remote = MagicMock()
                remote.videos.return_value.insert.return_value.next_chunk.return_value = (None, {'id': 'new-id'})
                snippet = {'title': package['title'], 'description': package['description_after'], 'channelId': 'test-channel'}
                status = {'privacyStatus': 'private', 'publishAt': when.isoformat()}
                remote.videos.return_value.list.return_value.execute.side_effect = [
                    {'items': [{'snippet': snippet}]}, {'items': [{'status': status}]},
                    {'items': [{'status': status}]}]
                config = {'work': 'work', 'channel_id': 'test-channel'}
                args = SimpleNamespace(job='job')
                with patch.object(run, 'auth', return_value=remote), patch('googleapiclient.http.MediaFileUpload'):
                    run.upload(config, args)
                    run.upload(config, args)
                self.assertEqual(remote.videos.return_value.insert.call_count, 1)
                self.assertEqual(remote.videos.return_value.update.call_count, 1)
                insertion = remote.videos.return_value.insert.call_args.kwargs['body']
                self.assertEqual(insertion['status']['privacyStatus'], 'private')
                self.assertNotIn('publishAt', insertion['status'])
                self.assertTrue(load(directory/'upload_state.json')['scheduled'])
                video.write_bytes(b'changed')
                with self.assertRaises(ValueError), patch.object(run, 'auth') as authentication:
                    run.upload(config, args)
                authentication.assert_not_called()
            finally:
                run.ROOT = original

    def test_concurrent_upload_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with run.upload_lock(directory):
                with self.assertRaises(ValueError):
                    with run.upload_lock(directory):
                        pass
            self.assertFalse((directory/'upload.lock').exists())

    def test_asset_import_integrity_and_repeatability(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            original = run.ROOT
            try:
                run.ROOT = Path(folder)
                pack = run.ROOT / 'assets'; pack.mkdir()
                cover = pack / 'cover.jpg'
                Image.new('RGB', (1280, 720), 'navy').save(cover)
                entry = {'job_id': 'job', 'title_zh': '剧名', 'titles': ['Title A', 'Title B', 'Title C'],
                         'drama_code': 'CODE', 'covers': ['cover.jpg']}
                save(pack/'manifest.json', {'jobs': [entry], 'sha256': {'cover.jpg': run.digest(cover)}})
                save(run.ROOT/'work/queue.json', [{'job_id': 'job', 'title_zh': '剧名',
                     'candidates': [{'drama_code': 'CODE'}]}])
                config = {'work': 'work'}; args = SimpleNamespace(pack=str(pack))
                run.import_pack(config, args)
                target = run.ROOT/'work/job/cover_1.jpg'
                self.assertEqual(run.digest(target), run.digest(cover))
                run.import_pack(config, args)
                self.assertFalse((target.parent/'approval.json').exists())
                cover.write_bytes(b'tampered')
                with self.assertRaises(ValueError): run.import_pack(config, args)
            finally:
                run.ROOT = original

    def test_review_preserves_description_and_requires_version(self):
        with tempfile.TemporaryDirectory() as folder:
            original = run.ROOT
            try:
                run.ROOT = Path(folder)
                directory = run.ROOT/'work/job'; directory.mkdir(parents=True)
                video=directory/'video.mp4';video.write_bytes(b'mock video')
                (directory/'cover_1.jpg').write_bytes(b'mock cover')
                description=directory/'description.txt';raw=b'Original  \r\n#tag\r\n\r\n';description.write_bytes(raw)
                when=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).isoformat()
                save(run.ROOT/'work/queue.json', [{'job_id':'job','publish_local':when,
                     'candidates':[{'drama_code':'A'},{'drama_code':'B'}]}])
                save(directory/'creative.json', {'titles':['Title A','Title B','Title C'],
                     'cover_count':1,'drama_code':None})
                args=SimpleNamespace(job='job',video=str(video),description=str(description),title=1,
                                     cover=1,code=None,publish_local=None)
                config={'work':'work','channel_id':'channel'}
                with self.assertRaises(ValueError):run.review(config,args)
                args.code='B';run.review(config,args)
                result=load(directory/'review.json')
                self.assertEqual(result['description_before'],raw.decode())
                self.assertEqual(result['description_after'],raw.decode()+'B')
                self.assertEqual(result['drama_code'],'B')
                self.assertFalse((directory/'approval.json').exists())
            finally:
                run.ROOT=original


if __name__ == '__main__':
    unittest.main()
