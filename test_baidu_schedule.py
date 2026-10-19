import csv
from pathlib import Path
import tempfile
import unittest

from baidu_download import build_tasks, schedule_rows


class ScheduleSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.schedule=self.root/'schedule.csv';self.resources=self.root/'resources.csv'
        rows=[['资源'],['剧名','代码']]
        for title in ['甲','乙','丙','丁']:
            row=['']*30;row[0]=title;row[1]=title+'CODE';row[29]='https://pan.baidu.com/s/demo';rows.append(row)
        self.write(self.resources,rows)
        self.write(self.schedule,[['日期','2026.10.20','2026.10.21','2026.10.22','2026.10.23'],
            ['俄语A','甲','','乙','丙'],['俄语B','丁','丙','甲','乙'],['新频道','乙','甲','','丁']])

    def tearDown(self):self.temp.cleanup()

    def write(self,path,rows):
        with path.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows(rows)

    def tasks(self,row=2,language='俄语',days=3,**kwargs):
        return build_tasks(self.schedule,self.resources,start='2026-10-20',days=days,
            row_selections=[dict(row=row,language=language)],**kwargs)

    def test_exact_row_days_not_count_of_nonempty_titles(self):
        result=self.tasks()
        self.assertEqual([(t['date'],t['title']) for t in result],[('2026-10-20','甲'),('2026-10-22','乙')])
        self.assertEqual([t['source_cell'] for t in result],['B2','D2'])
        self.assertEqual([t['title'] for t in self.tasks(row=3)],['丁','丙','甲'])

    def test_same_language_multiple_rows_are_not_guessed(self):
        with self.assertRaisesRegex(ValueError,'明确选择'):build_tasks(self.schedule,self.resources,['俄语'])
        self.assertEqual([r['row'] for r in schedule_rows(self.schedule)],[2,3,4])

    def test_unknown_row_language_requires_explicit_selection_and_conflicts_refused(self):
        self.assertIsNone(schedule_rows(self.schedule)[2]['language'])
        self.assertEqual(self.tasks(row=4,language='英语')[0]['language'],'英语')
        with self.assertRaisesRegex(ValueError,'不一致'):self.tasks(row=2,language='英语')

    def test_blank_header_skipped_until_explicit_inference_enabled(self):
        self.write(self.schedule,[['日期','2026.10.20','','2026.10.22'],['俄语频道','甲','丁','乙']])
        self.assertEqual([t['title'] for t in self.tasks()],['甲','乙'])
        result=self.tasks(infer_blank=True)
        self.assertEqual([t['title'] for t in result],['甲','丁','乙'])
        self.assertTrue(result[1]['inferred_date'])

    def test_day_one_two_titles_keeps_original_slot_order(self):
        self.write(self.schedule,[['日期','2026-10-20','2026-10-21'],['俄语频道','丁/甲','乙']])
        result=self.tasks(days=1)
        self.assertEqual([t['title'] for t in result],['丁','甲'])
        self.assertEqual([t['slot'] for t in result],[1,2])

    def test_duplicate_dates_and_missing_start_are_rejected(self):
        self.write(self.schedule,[['日期','2026.10.20','2026.10.20'],['俄语频道','甲','乙']])
        with self.assertRaisesRegex(ValueError,'重复'):self.tasks()
        self.write(self.schedule,[['日期','2026.10.21'],['俄语频道','乙']])
        with self.assertRaisesRegex(ValueError,'不存在'):self.tasks()

    def test_source_hash_changes_when_same_path_file_changes(self):
        before=self.tasks()[0]['schedule_sha256']
        with self.schedule.open('a',encoding='utf-8') as f:f.write('\n')
        self.assertNotEqual(self.tasks()[0]['schedule_sha256'],before)


if __name__=='__main__':unittest.main()
