import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from monitor_browser import installed_paths, launch_studio_browser

class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.engine=Mock();self.engine.executable_path=str(self.root/'absent-chromium')
    def test_machine_edge_location(self):
        exe=self.root/'Microsoft/Edge/Application/msedge.exe';exe.parent.mkdir(parents=True);exe.touch()
        with patch.dict(os.environ,{'PROGRAMFILES':str(self.root)},clear=True),patch('monitor_browser.shutil.which',return_value=None):
            self.assertIn(exe,list(installed_paths('msedge')))
    def test_auto_finds_chrome_when_edge_missing(self):
        exe=self.root/'chrome.exe';exe.touch()
        with patch('monitor_browser.installed_paths',side_effect=lambda k: iter([exe]) if k=='chrome' else iter([])):
            launch_studio_browser(self.engine,self.root/'profile',progress=lambda x:None)
        self.assertEqual(self.engine.launch_persistent_context.call_args.kwargs['executable_path'],str(exe))
    def test_bundled_chromium(self):
        exe=self.root/'chrome.exe';exe.touch();self.engine.executable_path=str(exe)
        with patch('monitor_browser.installed_paths',return_value=iter([])):
            launch_studio_browser(self.engine,self.root/'profile',progress=lambda x:None)
        self.assertEqual(self.engine.launch_persistent_context.call_args.kwargs['executable_path'],str(exe))
    def test_explicit_executable(self):
        exe=self.root/'chrome.exe';exe.touch()
        launch_studio_browser(self.engine,self.root/'profile',executable=str(exe),progress=lambda x:None)
        self.assertEqual(self.engine.launch_persistent_context.call_args.kwargs['executable_path'],str(exe))
    def test_missing_all_actionable_message(self):
        self.engine.launch_persistent_context.side_effect=RuntimeError('Chromium distribution not found')
        with patch('monitor_browser.installed_paths',return_value=iter([])):
            with self.assertRaisesRegex(ValueError,'install_monitor_browser_windows.bat'):
                launch_studio_browser(self.engine,self.root/'profile')
        self.assertEqual(self.engine.launch_persistent_context.call_count,3)
    def test_profile_error_not_hidden(self):
        self.engine.launch_persistent_context.side_effect=RuntimeError('user data directory is already in use')
        with patch('monitor_browser.installed_paths',return_value=iter([])):
            with self.assertRaisesRegex(RuntimeError,'already in use'):
                launch_studio_browser(self.engine,self.root/'profile')
        self.assertEqual(self.engine.launch_persistent_context.call_count,1)
    def test_explicit_missing_file(self):
        with self.assertRaisesRegex(ValueError,'不存在'):
            launch_studio_browser(self.engine,self.root/'profile',executable=str(self.root/'notfound.exe'))
        self.engine.launch_persistent_context.assert_not_called()
