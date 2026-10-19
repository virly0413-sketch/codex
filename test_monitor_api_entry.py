"""The default desktop click must scan API data without launching Studio."""
import queue
import unittest
from unittest.mock import Mock, patch
from monitor_desktop import App

class ApiEntryTests(unittest.TestCase):
    def test_default_click_exports_without_studio(self):
        app=App.__new__(App)
        app.busy=False;app.settings=Mock(return_value={'channel_id':'target'})
        app.events=queue.Queue();app.buttons=[Mock()];app.status=Mock()
        result=({'excel_video_count':1},'folder')
        class ImmediateThread:
            def __init__(self,target,daemon):self.target=target
            def start(self):self.target()
        with patch('monitor_desktop.threading.Thread',ImmediateThread), \
             patch('monitor_desktop.monitor.monitor_auth',return_value='api') as auth, \
             patch('monitor_desktop.monitor.scan',return_value=result) as scan, \
             patch('studio_revenue.scan_studio') as studio:
            app.start()
        auth.assert_called_once_with({'channel_id':'target'},reauthorize=False)
        scan.assert_called_once_with({'channel_id':'target'},youtube='api')
        studio.assert_not_called()
        self.assertEqual(app.events.get_nowait(),('result',result))
        self.assertEqual(app.events.get_nowait(),('done',None))
    def test_failed_api_reports_error_without_browser_fallback(self):
        app=App.__new__(App)
        app.busy=False;app.settings=Mock(return_value={});app.events=queue.Queue();app.buttons=[];app.status=Mock()
        class ImmediateThread:
            def __init__(self,target,daemon):self.target=target
            def start(self):self.target()
        with patch('monitor_desktop.threading.Thread',ImmediateThread), \
             patch('monitor_desktop.monitor.monitor_auth',side_effect=RuntimeError('API unavailable')), \
             patch('studio_revenue.scan_studio') as studio:
            app.start()
        self.assertEqual(app.events.get_nowait(),('error','API unavailable'))
        studio.assert_not_called()
