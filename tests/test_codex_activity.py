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

    def test_collector_cannot_overwrite_animation(self):
        result=m.outputs(self.norm(usage()))
        self.assertEqual(set(result), {'generated/codex-activity.json'})


if __name__=='__main__':unittest.main()
