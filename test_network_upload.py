import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from network_upload import inventory, matches, upload_private, existing_uploads
from baidu_download import atomic_json

class SharedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.task=dict(title='一介渔夫靠龙珠号令沧海',language='俄语',code='RU01',candidates=[{'code':'RU01'}])
    def add(self,name):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'video');return p
    def test_filename_and_folder(self):
        self.add('一介渔夫靠龙珠号令沧海俄语.mp4');self.add('一介渔夫靠龙珠号令沧海/俄语/全集.mp4')
        self.add('一介渔夫靠龙珠号令沧海英语.mp4');self.add('一介渔夫靠龙珠号令沧海续集俄语.mp4')
        self.assertEqual(len(matches(self.task,inventory(self.root))),2)
    def test_conflict_and_combined(self):
        self.add('一介渔夫靠龙珠号令沧海/俄语/全集英语.mp4');self.add('一介渔夫靠龙珠号令沧海英语俄语.mp4')
        self.assertEqual(matches(self.task,inventory(self.root)),[])
    def test_selected_root_language(self):
        self.add('俄语/一介渔夫靠龙珠号令沧海.mp4')
        self.assertEqual(len(matches(self.task,inventory(self.root/'俄语'))),1)
    def test_unavailable(self):
        with self.assertRaises(ValueError):inventory(self.root/'missing')
    def upload_setup(self):
        self.add('一介渔夫靠龙珠号令沧海俄语.mp4');f=inventory(self.root)[0]
        yt=Mock();request=yt.videos.return_value.insert.return_value
        request.next_chunk.return_value=(None,{'id':'newid'})
        return yt,request,f,self.root/'state.json'
    def test_private_and_idempotent(self):
        yt,req,f,state=self.upload_setup()
        config={'channel_id':'channel'}
        self.assertEqual(upload_private(yt,config,self.task,f,state),'newid')
        self.assertEqual(upload_private(yt,config,self.task,f,state),'newid')
        yt.videos.return_value.insert.assert_called_once()
        body=yt.videos.return_value.insert.call_args.kwargs['body']
        self.assertEqual(body['status']['privacyStatus'],'private')
        self.assertNotIn('publishAt',body['status'])
        self.assertEqual(body['snippet']['description'],'RU01')
    def test_uncertain_not_retried(self):
        yt,req,f,state=self.upload_setup();req.next_chunk.side_effect=TimeoutError('timeout')
        with self.assertRaises(TimeoutError):upload_private(yt,{'channel_id':'channel'},self.task,f,state)
        with self.assertRaisesRegex(ValueError,'未确认'):upload_private(yt,{'channel_id':'channel'},self.task,f,state)
        yt.videos.return_value.insert.assert_called_once()
    def test_changed_source(self):
        yt,req,f,state=self.upload_setup();Path(f['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'更改'):upload_private(yt,{'channel_id':'channel'},self.task,f,state)
        yt.videos.return_value.insert.assert_not_called()
    def test_correct_channel_playlist(self):
        yt=Mock()
        responses=[{'items':[{'id':'other','contentDetails':{'relatedPlaylists':{'uploads':'wrong'}}},
                            {'id':'target','contentDetails':{'relatedPlaylists':{'uploads':'right'}}}]},
                   {'items':[{'snippet':{'title':'剧名'},'contentDetails':{'videoId':'existing'}}]}]
        with patch('network_upload.read_request',side_effect=responses):
            self.assertEqual(existing_uploads(yt,'target'),{'剧名':['existing']})
        self.assertEqual(yt.playlistItems.return_value.list.call_args.kwargs['playlistId'],'right')

if __name__=='__main__':unittest.main()
