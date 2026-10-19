import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from baidu_browser import ClientHandoffNotStarted, DownloadUnavailable
from baidu_client import ClientDownloads, matching_name
from baidu_runner import run_downloads


class ClientDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.inbox=self.root/'中转';self.inbox.mkdir()
        self.payload=b'\x00\x00\x00\x18ftypisom'+b'video payload'*20
        self.item=dict(id='100',name='剧名俄语.mp4',size=len(self.payload),parents=[],isdir=False,
            md5=hashlib.md5(self.payload).hexdigest())
        self.share={'url':'https://pan.baidu.com/s/demo','password':'abcd'}
        self.browser=MagicMock();self.browser.inventory.return_value=[self.item]
        self.target=self.root/'俄语'/'target.mp4'

    def tearDown(self):self.temp.cleanup()

    def adapter(self,timeout=.1):
        return ClientDownloads(self.browser,self.inbox,self.root/'work',log=lambda _:None,
            timeout_seconds=timeout,stable_seconds=0,poll_seconds=.001)

    def test_client_handoff_routes_new_completed_file(self):
        self.browser.queue_client.side_effect=lambda *args:(self.inbox/self.item['name']).write_bytes(self.payload)
        self.adapter().download(self.share,self.item,self.target)
        self.assertEqual(self.target.read_bytes(),self.payload)
        self.assertFalse((self.inbox/self.item['name']).exists())
        self.browser.queue_client.assert_called_once()

    def test_old_inbox_file_untouched_new_duplicate_is_routed(self):
        old=self.inbox/self.item['name'];old.write_bytes(self.payload)
        new=self.inbox/'剧名俄语(1).mp4'
        self.browser.queue_client.side_effect=lambda *args:new.write_bytes(self.payload)
        self.adapter().download(self.share,self.item,self.target)
        self.assertEqual(old.read_bytes(),self.payload)
        self.assertFalse(new.exists());self.assertEqual(self.target.read_bytes(),self.payload)

    def test_pending_task_survives_restart_and_is_not_sent_twice(self):
        self.browser.queue_client.return_value=None
        with self.assertRaises(DownloadUnavailable):self.adapter(.01).download(self.share,self.item,self.target)
        self.assertFalse(self.target.exists())
        self.assertTrue((self.root/'work'/'client_pending.json').exists())
        (self.inbox/self.item['name']).write_bytes(self.payload)
        self.adapter().download(self.share,self.item,self.target)
        self.assertEqual(self.target.read_bytes(),self.payload)
        self.assertEqual(self.browser.queue_client.call_count,1)

    def test_temporary_companion_and_wrong_md5_are_not_complete(self):
        source=self.inbox/self.item['name'];part=Path(str(source)+'.baiduyun.downloading')
        def enqueue(*args):source.write_bytes(self.payload);part.write_bytes(b'partial')
        self.browser.queue_client.side_effect=enqueue
        with self.assertRaises(DownloadUnavailable):self.adapter(.01).download(self.share,self.item,self.target)
        part.unlink();source.write_bytes(b'x'*len(self.payload))
        with self.assertRaises(DownloadUnavailable):self.adapter(.01).download(self.share,self.item,self.target)
        self.assertFalse(self.target.exists());self.assertTrue(source.exists())
        source.write_bytes(self.payload);self.adapter().download(self.share,self.item,self.target)
        self.assertTrue(self.target.exists())

    def test_existing_destination_never_overwritten(self):
        self.target.parent.mkdir();self.target.write_bytes(b'user file')
        with self.assertRaises(ValueError):self.adapter().download(self.share,self.item,self.target)
        self.browser.queue_client.assert_not_called()
        self.assertEqual(self.target.read_bytes(),b'user file')

    def test_failure_before_request_does_not_leave_false_sent_state(self):
        self.browser.queue_client.side_effect=ClientHandoffNotStarted('未定位到文件行')
        with self.assertRaises(ClientHandoffNotStarted):self.adapter().download(self.share,self.item,self.target)
        self.browser.queue_client.side_effect=lambda *args:(self.inbox/self.item['name']).write_bytes(self.payload)
        self.adapter().download(self.share,self.item,self.target)
        self.assertEqual(self.browser.queue_client.call_count,2)
        self.assertEqual(self.target.read_bytes(),self.payload)

    def test_inbox_must_be_independent_and_duplicate_names_match(self):
        with self.assertRaises(ValueError):self.adapter().download(self.share,self.item,self.inbox/'target.mp4')
        self.assertTrue(matching_name('剧名俄语（2）.mp4','剧名俄语.mp4'))
        self.assertFalse(matching_name('另一个剧俄语.mp4','剧名俄语.mp4'))

    def test_real_client_file_and_runner_create_verified_record(self):
        self.browser.queue_client.side_effect=lambda *args:(self.inbox/self.item['name']).write_bytes(self.payload)
        task=dict(id='task',date='2026-10-20',title='排片剧名',language='俄语',code='CODE',share=self.share,candidates=[])
        records=run_downloads([task],{'俄语':self.root/'俄语'},self.root/'work',self.adapter(),log=lambda _:None)
        self.assertEqual(records[0]['状态'],'下载完成')
        self.assertEqual(Path(records[0]['本地文件']).parent,self.root/'俄语')
        self.assertTrue((self.root/'work'/'downloads.json').exists())


if __name__=='__main__':unittest.main()
