import unittest
from datetime import date
from moment_calendar import danish_days, occasion_for_dates, title_for
from moments_engine import discover


class CalendarTests(unittest.TestCase):
    def test_movable_dates_are_calculated_per_year(self):
        self.assertEqual(danish_days(2026)[date(2026,4,5)][0], 'Påskedag')
        self.assertEqual(danish_days(2027)[date(2027,3,28)][0], 'Påskedag')
        self.assertEqual(danish_days(2026)[date(2026,5,24)][0], 'Pinsedag')
        self.assertEqual(danish_days(2026)[date(2026,5,14)][0], 'Kristi himmelfartsdag')

    def test_common_holidays_and_country_specific_days(self):
        occasion = occasion_for_dates([date(2026,12,24)]*8, ['DK'])
        self.assertEqual(title_for(occasion), 'Juleaften 2026')
        self.assertEqual(title_for(occasion,'Tivoli'), 'Juleaften i Tivoli')
        self.assertIsNone(occasion_for_dates([date(2026,6,5)]*8,['DE']))
        self.assertEqual(occasion_for_dates([date(2026,12,31),date(2027,1,1)],['DK'])['name'],'Nytår')
        self.assertIsNone(occasion_for_dates([date(2026,12,24)]+[date(2026,12,20)]*8,['DK']))

    def test_christmas_at_home_can_be_a_moment(self):
        rows=[dict(id=i,captured_at=f'2026-12-24T{10+i}:00:00',gps_name='Næstved, Denmark') for i in range(8)]
        moments,_,_=discover(rows,manual_home={'name':'Næstved, Denmark'})
        self.assertEqual(moments[0]['title'],'Juleaften 2026')
        self.assertEqual(moments[0]['evidence']['occasion']['basis'],'capture_date')

    def test_import_date_alone_does_not_create_a_christmas_label(self):
        rows=[dict(id=i,modified_fs=f'2026-12-24T{10+i}:00:00',gps_name='Berlin, Germany') for i in range(8)]
        moments,_,_=discover(rows)
        self.assertTrue(moments)
        self.assertIsNone(moments[0]['evidence']['occasion'])
