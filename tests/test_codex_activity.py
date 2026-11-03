import copy
from datetime import date
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('codex_activity', Path(__file__).resolve().parents[1]/'scripts/codex_activity.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def usage():
    return {'summary': {'lifetimeTokens': 200, 'peakDailyTokens': 120,
            'longestRunningTurnSec': 3600, 'currentStreakDays': 2, 'longestStreakDays': 2},
            'dailyUsageBuckets': [{'startDate':'2026-11-01','tokens':80}, {'startDate':'2026-11-02','tokens':120}]}


class UsageTests(unittest.TestCase):
    def norm(self, raw): return m.normalize(raw, date(2026,11,3))

    def test_missing_or_empty_is_not_zero_activity(self):
        for buckets in (None, [], [{'startDate':'2026-11-02','tokens':0}]):
            raw=usage(); raw['dailyUsageBuckets']=buckets
            with self.assertRaises(ValueError): self.norm(raw)

    def test_reject_duplicate_future_negative_and_wrong_totals(self):
        for replacement in ({'startDate':'2026-11-01','tokens':120},
                            {'startDate':'2026-11-04','tokens':120},
                            {'startDate':'2026-11-02','tokens':-1},
                            {'startDate':'2026-11-02','tokens':121}):
            raw=usage();raw['dailyUsageBuckets'][1]=replacement
            with self.assertRaises(ValueError): self.norm(raw)

    def test_stale_data_and_summary_regression_fail_closed(self):
        with self.assertRaises(ValueError): m.normalize(usage(), date(2026,11,15))
        previous=self.norm(usage());current=copy.deepcopy(previous)
        current['summary']['lifetimeTokens']=199
        with self.assertRaises(ValueError):m.check_regression(current,previous)

    def test_only_aggregates_are_exported(self):
        raw=usage();raw['email']='private@example.com';raw['summary']['secret']='do-not-export'
        result=m.outputs(self.norm(raw))
        self.assertNotIn('private@example.com',str(result))
        self.assertNotIn('do-not-export',str(result))

    def test_calendar_preserves_counts_and_handles_week_boundary(self):
        data=self.norm(usage())
        for theme in ['dark','light']:
            root=ET.fromstring(m.render(data,theme))
            cells=[n for n in root if n.get('data-date')]
            self.assertEqual(len(cells),366)
            self.assertEqual(cells[-1].get('data-date'),'2026-11-02')
            self.assertEqual(sum(int(n.get('data-tokens')) for n in cells),200)
            self.assertEqual(len(set(n.get('data-date') for n in cells)),len(cells))
            self.assertTrue(all(n.tag.rsplit('}',1)[-1] not in {'script','foreignObject','image'} for n in root.iter()))

    def test_missing_optional_summary_is_visible(self):
        raw=usage();raw['summary']['longestRunningTurnSec']=None
        self.assertIn('—',m.render(self.norm(raw),'dark'))


if __name__=='__main__':unittest.main()
