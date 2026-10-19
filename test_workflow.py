import argparse
import contextlib
import csv
import copy
import datetime as dt
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import run
import networking
from prepare import description_with_code, prepare

RELEASE_ROOT = run.ROOT


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_root = run.ROOT
        run.ROOT = Path(self.temp.name)
        self.config = {'work':'local_work','channel_id':'channel'}
        self.directory = run.ROOT / 'local_work/job'
        self.directory.mkdir(parents=True)
        self.cover = self.directory/'cover_1.jpg'
        self.cover.write_bytes(b'mocked thumbnail transport')
        self.when = (dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).replace(microsecond=0)
        run.save(run.ROOT/'local_work/queue.json', [{'job_id':'job','title_zh':'太初神帝',
            'publish_local':self.when.isoformat(),'candidates':[{'drama_code':'CODE'}]}])
        run.save(self.directory/'creative.json', {'titles':['Title A','Title B','Title C'],
            'cover_count':1,'drama_code':'CODE'})
        self.video = {'id':'existing123','etag':'version0', 'snippet':{
            'channelId':'channel','title':'《太初神帝》完整版','description':'Original  \r\n#tag\r\n\r\n',
            'categoryId':'24','tags':['keep','tags'],'defaultLanguage':'zh',
            'defaultAudioLanguage':'en','thumbnails':{'high':{'url':'https://example.com/old.jpg'}}},
            'status':{'privacyStatus':'private','uploadStatus':'processed','license':'youtube',
                      'embeddable':True,'publicStatsViewable':True,'selfDeclaredMadeForKids':False}}
        self.args=argparse.Namespace(job='job',video_id='existing123',code=None,title=1,cover=1,publish_local=None)

    def tearDown(self):
        run.ROOT = self.old_root
        self.temp.cleanup()

    def remote(self, videos):
        remote=MagicMock()
        remote.videos.return_value.list.return_value.execute.side_effect=[{'items':[v]} for v in videos]
        remote.videos.return_value.update.return_value.headers={}
        return remote

    def review_and_approve(self):
        with patch.object(run,'auth',return_value=self.remote([copy.deepcopy(self.video)])), contextlib.redirect_stdout(io.StringIO()):
            run.review(self.config,self.args)
            package=run.load(self.directory/'review.json')
            run.approve(self.config,argparse.Namespace(job='job',fingerprint=run.fingerprint(package)))
        return package

    def after_video(self, package):
        after=copy.deepcopy(self.video)
        after['etag']='version2'
        after['snippet']['title']=package['title']
        after['snippet']['description']=package['description_after']
        after['status']['publishAt']=package['publish_at']
        return after

    def test_description_preserves_original_and_does_not_duplicate(self):
        for original in ['', 'Text  ', 'Text\r\n\r\n', '#tag\nlink']:
            result=description_with_code(original,'CODE')
            self.assertTrue(result.startswith(original))
            self.assertEqual(result.splitlines()[-1],'CODE')
            self.assertEqual(description_with_code(result,'CODE'),result)
        with self.assertRaises(ValueError):description_with_code('text','a\nb')

    def test_bundled_schedule_and_assets(self):
        queue=run.load(RELEASE_ROOT/'data/jobs.json')
        assets=run.load(RELEASE_ROOT/'assets/manifest.json')['jobs']
        self.assertEqual(len(queue),8)
        self.assertEqual({j['job_id'] for j in queue},{j['job_id'] for j in assets})
        first=[j for j in queue if j['date']=='2026-10-22']
        self.assertEqual([j['publish_at'] for j in first],['2026-10-22T09:00:00Z','2026-10-22T13:00:00Z'])
        for j in assets:
            for name in j['covers']:
                self.assertEqual(run.digest(RELEASE_ROOT/'assets'/name),run.load(RELEASE_ROOT/'assets/manifest.json')['sha256'][name])

    def test_review_fetches_existing_description_read_only(self):
        remote=self.remote([self.video])
        with patch.object(run,'auth',return_value=remote),contextlib.redirect_stdout(io.StringIO()):
            run.review(self.config,self.args)
        package=run.load(self.directory/'review.json')
        original=self.video['snippet']['description']
        self.assertEqual(package['description_before'],original)
        self.assertEqual(package['description_after'],original+'CODE')
        self.assertEqual(package['video_id'],'existing123')
        self.assertNotIn('video',package)
        remote.videos.return_value.update.assert_not_called()
        remote.videos.return_value.insert.assert_not_called()
        remote.thumbnails.return_value.set.assert_not_called()
        self.assertFalse((self.directory/'approval.json').exists())

    def test_title_matching_and_ambiguity_require_selection(self):
        self.assertEqual(len(run.match_videos('太初神帝',[self.video])),1)
        run.save(run.ROOT/'local_work/channel_videos.json',[self.video,dict(self.video,id='duplicate')])
        self.args.video_id=None
        with patch.object(run,'auth') as authentication,self.assertRaises(ValueError):
            run.review(self.config,self.args)
        authentication.assert_not_called()

    def test_scan_paginates_upload_playlist_and_video_batches(self):
        remote=MagicMock()
        remote.channels.return_value.list.return_value.execute.return_value={'items':[{'contentDetails':{'relatedPlaylists':{'uploads':'uploads'}}}]}
        remote.playlistItems.return_value.list.return_value.execute.side_effect=[
            {'items':[{'contentDetails':{'videoId':str(i)}} for i in range(50)],'nextPageToken':'page2'},
            {'items':[{'contentDetails':{'videoId':str(i)}} for i in range(50,55)]}]
        remote.videos.return_value.list.return_value.execute.side_effect=[{'items':[self.video]},{'items':[]}]
        with patch.object(run,'auth',return_value=remote),contextlib.redirect_stdout(io.StringIO()):run.scan(self.config)
        self.assertEqual(remote.playlistItems.return_value.list.call_count,2)
        self.assertEqual(remote.videos.return_value.list.call_count,2)
        remote.videos.return_value.update.assert_not_called()
        self.assertTrue((run.ROOT/'local_work/channel_videos.json').exists())

    def test_public_video_rejected_without_mutation(self):
        video=copy.deepcopy(self.video);video['status']['privacyStatus']='public'
        remote=self.remote([video])
        with patch.object(run,'auth',return_value=remote),self.assertRaises(ValueError):run.review(self.config,self.args)
        remote.videos.return_value.update.assert_not_called()

    def test_stale_review_and_legacy_approval_rejected(self):
        package=self.review_and_approve()
        package['title']='changed';run.save(self.directory/'review.json',package)
        with patch.object(run,'auth') as authentication,self.assertRaises(ValueError):run.apply_changes(self.config,self.args)
        authentication.assert_not_called()
        run.save(self.directory/'review.json',{'title':'legacy','demo':False})
        with self.assertRaises(ValueError):run.approve(self.config,argparse.Namespace(job='job',fingerprint='bad'))

    def test_remote_edit_after_approval_blocks_all_mutations(self):
        self.review_and_approve()
        changed=copy.deepcopy(self.video);changed['snippet']['description']='Manually edited'
        remote=self.remote([changed])
        with patch.object(run,'auth',return_value=remote),self.assertRaises(ValueError):run.apply_changes(self.config,self.args)
        remote.thumbnails.return_value.set.assert_not_called()
        remote.videos.return_value.update.assert_not_called()

    def test_apply_preserves_fields_no_upload_and_repeat_is_idempotent(self):
        package=self.review_and_approve()
        thumb=copy.deepcopy(self.video);thumb['etag']='version1'
        final=self.after_video(package)
        remote=self.remote([self.video,thumb,final,final])
        with patch.object(run,'auth',return_value=remote),patch('googleapiclient.http.MediaFileUpload'),contextlib.redirect_stdout(io.StringIO()):
            run.apply_changes(self.config,self.args)
            run.apply_changes(self.config,self.args)
        remote.videos.return_value.insert.assert_not_called()
        self.assertEqual(remote.videos.return_value.update.call_count,1)
        self.assertEqual(remote.thumbnails.return_value.set.call_count,1)
        body=remote.videos.return_value.update.call_args.kwargs['body']
        self.assertEqual(body['id'],'existing123')
        self.assertEqual(body['snippet']['tags'],['keep','tags'])
        self.assertEqual(body['snippet']['defaultAudioLanguage'],'en')
        self.assertEqual(body['snippet']['categoryId'],'24')
        self.assertEqual(body['status']['license'],'youtube')
        self.assertEqual(body['status']['selfDeclaredMadeForKids'],False)
        self.assertEqual(remote.videos.return_value.update.return_value.headers['If-Match'],'version1')
        self.assertEqual(run.load(self.directory/'apply_state.json')['stage'],'done')

    def test_uncertain_thumbnail_failure_does_not_blindly_retry(self):
        self.review_and_approve()
        remote=self.remote([self.video,self.video])
        remote.thumbnails.return_value.set.return_value.execute.side_effect=RuntimeError('timeout')
        with patch.object(run,'auth',return_value=remote),patch('googleapiclient.http.MediaFileUpload'):
            with self.assertRaises(RuntimeError):run.apply_changes(self.config,self.args)
            with self.assertRaises(ValueError):run.apply_changes(self.config,self.args)
        self.assertEqual(remote.thumbnails.return_value.set.call_count,1)
        remote.videos.return_value.update.assert_not_called()

    def test_thumbnail_tampering_stops_before_auth(self):
        self.review_and_approve();self.cover.write_bytes(b'changed')
        with patch.object(run,'auth') as authentication,self.assertRaises(ValueError):run.apply_changes(self.config,self.args)
        authentication.assert_not_called()

    def test_metadata_timeout_reconciles_success_without_second_write(self):
        package=self.review_and_approve()
        thumb=copy.deepcopy(self.video);thumb['etag']='version1'
        final=self.after_video(package)
        remote=self.remote([self.video,thumb,final])
        remote.videos.return_value.update.return_value.execute.side_effect=RuntimeError('response lost')
        with patch.object(run,'auth',return_value=remote),patch('googleapiclient.http.MediaFileUpload'),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):run.apply_changes(self.config,self.args)
            run.apply_changes(self.config,self.args)
        self.assertEqual(remote.videos.return_value.update.call_count,1)
        self.assertEqual(remote.thumbnails.return_value.set.call_count,1)
        self.assertEqual(run.load(self.directory/'apply_state.json')['stage'],'done')

    def test_known_server_normalizations_and_added_defaults(self):
        package=self.review_and_approve(); expected=run.desired_state(package)
        actual=copy.deepcopy(expected)
        actual['status']['containsSyntheticMedia']=False
        actual['status']['publishAt']=self.when.astimezone(dt.timezone(dt.timedelta(hours=8))).isoformat()
        actual['snippet']['tags'].reverse()
        actual['snippet']['defaultLanguage']='ZH'
        differences,added=run.state_differences(expected,actual)
        self.assertEqual(differences,[])
        self.assertEqual(added['status']['containsSyntheticMedia'],False)

    def test_verification_polls_reads_without_resending_writes(self):
        package=self.review_and_approve()
        thumb=copy.deepcopy(self.video);thumb['etag']='version1'
        final=self.after_video(package);final['status']['containsSyntheticMedia']=False
        remote=self.remote([self.video,thumb,self.video,final])
        with patch.object(run,'auth',return_value=remote),patch('googleapiclient.http.MediaFileUpload'), \
             patch.object(run.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
            run.apply_changes(self.config,self.args)
        self.assertEqual(remote.videos.return_value.update.call_count,1)
        self.assertEqual(remote.thumbnails.return_value.set.call_count,1)
        self.assertTrue(run.load(self.directory/'verification.json')['metadata_and_schedule_confirmed'])

    def test_wrong_description_or_schedule_stays_unconfirmed_with_field_report(self):
        package=self.review_and_approve();video=self.after_video(package)
        video['snippet']['description']='Wrong description'
        video['status']['publishAt']=(self.when+dt.timedelta(hours=1)).isoformat()
        remote=self.remote([video,video,video])
        with patch.object(run.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'snippet.description'):
                run.verify_result(remote,self.config,package,self.directory)
        report=run.load(self.directory/'verification.json')
        self.assertFalse(report['metadata_and_schedule_confirmed'])
        self.assertEqual({d['field'] for d in report['differences']},{'snippet.description','status.publishAt'})
        remote.videos.return_value.update.assert_not_called()
        remote.thumbnails.return_value.set.assert_not_called()

    def test_read_only_verify_recovers_old_uncertain_result_without_mutations(self):
        package=self.review_and_approve();video=self.after_video(package)
        video['status']['containsSyntheticMedia']=False
        remote=self.remote([video])
        run.save(self.directory/'apply_state.json',{'stage':'metadata_started','fingerprint':run.fingerprint(package)})
        with patch.object(run,'auth',return_value=remote),contextlib.redirect_stdout(io.StringIO()):
            run.verify_existing(self.config,self.args)
        self.assertTrue(run.load(self.directory/'verification.json')['metadata_and_schedule_confirmed'])
        remote.videos.return_value.update.assert_not_called()
        remote.thumbnails.return_value.set.assert_not_called()

    def test_single_publish_action_needs_no_separate_approval_and_is_idempotent(self):
        thumb=copy.deepcopy(self.video);thumb['etag']='version1'
        final=self.after_video({'title':'Title A','description_after':self.video['snippet']['description']+'CODE',
                               'publish_at':self.when.isoformat().replace('+00:00','Z')})
        remote=self.remote([self.video,self.video,thumb,final,final])
        with patch.object(run,'auth',return_value=remote),patch('googleapiclient.http.MediaFileUpload'), \
             patch.object(run,'approve') as separate_approval,contextlib.redirect_stdout(io.StringIO()):
            run.publish(self.config,self.args)
            run.publish(self.config,self.args)
        separate_approval.assert_not_called()
        self.assertEqual(remote.videos.return_value.update.call_count,1)
        self.assertEqual(run.load(self.directory/'approval.json')['authorization'],'explicit_publish_action')

    def test_single_publish_does_not_guess_ambiguous_video(self):
        self.args.video_id=None
        run.save(run.ROOT/'local_work/channel_videos.json',[self.video,dict(self.video,id='other')])
        with patch.object(run,'auth') as authentication,self.assertRaises(ValueError):
            run.publish(self.config,self.args)
        authentication.assert_not_called()
        self.assertFalse((self.directory/'approval.json').exists())

    def test_russian_profile_has_its_own_schedule_and_is_isolated(self):
        ru=run.load(RELEASE_ROOT/'profiles/russian.json')
        en=run.load(RELEASE_ROOT/'profiles/english.json')
        self.assertEqual(ru['channel_id'],'UC_o03Jz0Ek8xYGE_oy3zapg')
        self.assertNotEqual(ru['work'],en['work'])
        self.assertNotEqual(ru['oauth_token'],en['oauth_token'])
        ru['planning_source']=str(RELEASE_ROOT/ru['planning_source'])
        with contextlib.redirect_stdout(io.StringIO()):
            run.plan(ru)
            run.import_pack(ru,argparse.Namespace(pack=str(RELEASE_ROOT/ru['assets_path'])))
        jobs=run.load(run.ROOT/ru['work']/'queue.json')
        self.assertEqual(len(jobs),22)
        self.assertEqual(min(j['date'] for j in jobs),'2026-10-20')
        self.assertEqual(max(j['date'] for j in jobs),'2026-11-10')
        self.assertTrue(all(j['channel_id']==ru['channel_id'] and j['language']=='ru' for j in jobs))
        self.assertTrue(all(j['publish_local'][11:16]=='17:00' for j in jobs))
        manifest=run.load(RELEASE_ROOT/ru['assets_path']/'manifest.json')
        self.assertEqual({j['job_id'] for j in jobs},{j['job_id'] for j in manifest['jobs']})
        for j in manifest['jobs']:
            self.assertEqual(len(j['titles']),3)
            for title in j['titles']:
                self.assertLessEqual(len(title),100)
            for cover in j['covers']:
                self.assertEqual(run.digest(RELEASE_ROOT/ru['assets_path']/cover),manifest['sha256'][cover])
        with self.assertRaisesRegex(ValueError,'其他频道'):
            run.import_pack(en,argparse.Namespace(pack=str(RELEASE_ROOT/ru['assets_path'])))

    def test_russian_ambiguous_version_does_not_guess_code(self):
        ru=run.load(RELEASE_ROOT/'profiles/russian.json')
        entries=run.load(RELEASE_ROOT/ru['planning_source'])
        hammer=next(j for j in entries if j['title_zh']=='武魂觉醒我用锤子一人成军')
        self.assertEqual({c['drama_code'] for c in hammer['candidates']},{'2609 KR64','2026 WW52'})
        manifest=run.load(RELEASE_ROOT/ru['assets_path']/'manifest.json')
        asset=next(j for j in manifest['jobs'] if j['job_id']==hammer['job_id'])
        self.assertIsNone(asset['drama_code'])
        run.save(run.ROOT/'local_work/queue.json',[dict(hammer,job_id='job')])
        run.save(self.directory/'creative.json',dict(asset,cover_count=1))
        args=argparse.Namespace(job='job',title=1,cover=1,code=None,video_id='existing123',publish_local=None)
        with patch.object(run,'auth') as authentication,self.assertRaisesRegex(ValueError,'exact resource version'):
            run.review(self.config,args)
        authentication.assert_not_called()

    def test_desktop_publish_button_retains_callable_after_time_field_creation(self):
        import desktop
        config=run.load(RELEASE_ROOT/'profiles/russian.json')
        with contextlib.ExitStack() as stack:
            for name in ['Frame','Label','Entry','Treeview','Combobox']:
                stack.enter_context(patch.object(desktop.ttk,name))
            buttons=stack.enter_context(patch.object(desktop.ttk,'Button'))
            stack.enter_context(patch.object(desktop.tk,'StringVar'))
            stack.enter_context(patch.object(desktop.tk,'Text'))
            stack.enter_context(patch.object(desktop.App,'refresh'))
            stack.enter_context(patch.object(desktop.run,'load',return_value=config))
            app=desktop.App(MagicMock(),RELEASE_ROOT/'profiles/russian.json')
        callback=next(call.kwargs['command'] for call in buttons.call_args_list
                      if call.kwargs.get('text')=='发布（按所选时间定时公开）')
        self.assertTrue(callable(callback))
        self.assertEqual(callback,app.publish)
        self.assertEqual(app.config_path,RELEASE_ROOT/'profiles/russian.json')

    def test_csv_reader_uses_russian_audio_column(self):
        schedule=run.ROOT/'schedule.csv';resource=run.ROOT/'resource.csv'
        with schedule.open('w',encoding='utf-8',newline='') as f:
            csv.writer(f).writerows([['日期','2026.10.18'],['俄语男频','示例']])
        header=['']*30;header[4]='英语';header[14]='俄语'
        row=['']*30;row[0]='《示例》';row[1]='CODE';row[14]='有'
        with resource.open('w',encoding='utf-8',newline='') as f:
            csv.writer(f).writerows([['']*30,header,row])
        ru=prepare(schedule,resource,'俄语男频',dt.date(2026,10,16),language='ru')[0]
        en=prepare(schedule,resource,'俄语男频',dt.date(2026,10,16),language='en')[0]
        self.assertEqual(ru['candidates'][0]['audio_availability'],'有')
        self.assertNotIn('ru_audio_availability_unverified',ru['blockers'])
        self.assertIn('en_audio_availability_unverified',en['blockers'])

    def test_concurrent_operation_lock(self):
        with run.upload_lock(self.directory):
            with self.assertRaises(ValueError):
                with run.upload_lock(self.directory):pass
        self.assertFalse((self.directory/'upload.lock').exists())

    def test_proxy_shared_by_requests_and_api_transport(self):
        config={'proxy_url':'http://127.0.0.1:7890','http_timeout_seconds':17}
        session=networking.requests_session(config)
        self.assertFalse(session.trust_env)
        self.assertEqual(session.proxies['https'],config['proxy_url'])
        transport=networking.http_transport(config)
        self.assertEqual(transport.timeout,17)
        self.assertEqual(transport.proxy_info.proxy_host,'127.0.0.1')
        self.assertEqual(transport.proxy_info.proxy_port,7890)
        transport=networking.http_transport({'proxy_url':'socks5h://127.0.0.1:1080'})
        self.assertTrue(transport.proxy_info.proxy_rdns)

    def test_invalid_proxy_and_timeout_rejected(self):
        for value in ['https://127.0.0.1:7890','http://user:pass@localhost:8080','127.0.0.1:7890','http://localhost:port']:
            with self.assertRaises(ValueError):networking.proxy_url({'proxy_url':value})
        with self.assertRaises(ValueError):networking.timeout_seconds({'http_timeout_seconds':1})

    def test_safe_read_retry_and_actionable_error(self):
        request=MagicMock()
        request.execute.side_effect=TimeoutError('connection timed out')
        with self.assertRaisesRegex(RuntimeError,'代理'):
            networking.read_request(request,'扫描')
        request.execute.assert_called_once_with(num_retries=2)

    def test_channel_mismatch_shows_actual_and_does_not_change_target(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Other channel'):
                run.verify_channel(self.config,[{'id':'wrong','snippet':{'title':'Other channel'}}])
            run.verify_channel(self.config,[{'id':'channel','snippet':{'title':'Right channel'}}])
            with self.assertRaisesRegex(ValueError,'无频道'):
                run.verify_channel(self.config,[])
        self.assertEqual(self.config['channel_id'],'channel')

    def test_failed_channel_switch_preserves_previous_token(self):
        config=dict(self.config,oauth_token='token.json',oauth_client='client_secret.json')
        token=run.ROOT/'token.json';token.write_text('previous-local-token')
        flow=MagicMock();credentials=MagicMock()
        credentials.to_json.return_value='new-matched-token'
        flow.run_local_server.return_value=credentials
        youtube=MagicMock()
        result=youtube.channels.return_value.list.return_value.execute
        result.return_value={'items':[{'id':'wrong','snippet':{'title':'Personal channel'}}]}
        with patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',return_value=flow), \
             patch('google_auth_httplib2.AuthorizedHttp'), \
             patch('googleapiclient.discovery.build',return_value=youtube), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):run.auth(config,reauthorize=True)
            self.assertEqual(token.read_text(),'previous-local-token')
            result.return_value={'items':[{'id':'channel','snippet':{'title':'Supreme Hero Flicks'}}]}
            run.auth(config,reauthorize=True)
        self.assertEqual(token.read_text(),'new-matched-token')
        self.assertIn('select_account',flow.run_local_server.call_args.kwargs['prompt'])


if __name__=='__main__':unittest.main()
