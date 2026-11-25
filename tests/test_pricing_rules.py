"""Unit tests for the pure pricing functions: BR-01 .. BR-06, BR-10."""
import unittest
from datetime import date
from decimal import Decimal as D

from amc import pricing
from amc.dates import add_months


class TestBR01Base(unittest.TestCase):
    def test_BR01_basic_6_percent(self):
        self.assertEqual(pricing.base_value(D(100000), D(6)), D(6000))

    def test_BR01_comprehensive_10_percent(self):
        self.assertEqual(pricing.base_value(D(100000), D(10)), D(10000))

    def test_BR01_premium_14_percent(self):
        self.assertEqual(pricing.base_value(D(100000), D(14)), D(14000))


class TestBR02AgeSurcharge(unittest.TestCase):
    start = date(2026, 6, 1)

    def test_BR02_older_than_8_comprehensive_gets_25_percent(self):
        self.assertEqual(pricing.base_with_age(D(100000), D(10), date(2018, 1, 1), self.start, "COMPREHENSIVE"), D(12500))

    def test_BR02_older_than_8_premium_gets_25_percent(self):
        self.assertEqual(pricing.base_with_age(D(100000), D(14), date(2018, 1, 1), self.start, "PREMIUM"), D(17500))

    def test_BR02_basic_never_gets_surcharge(self):
        self.assertEqual(pricing.base_with_age(D(100000), D(6), date(2010, 1, 1), self.start, "BASIC"), D(6000))

    def test_BR02_exactly_8_years_old_no_surcharge(self):
        self.assertFalse(pricing.age_surcharge_applies(date(2018, 6, 1), self.start, "PREMIUM"))

    def test_BR02_one_day_over_8_years_gets_surcharge(self):
        self.assertTrue(pricing.age_surcharge_applies(date(2018, 5, 31), self.start, "PREMIUM"))

    def test_BR02_edge_turning_8_during_new_term_no_surcharge(self):
        self.assertFalse(pricing.age_surcharge_applies(date(2018, 9, 1), self.start, "COMPREHENSIVE"))


class TestBR03Escalation(unittest.TestCase):
    def test_BR03_previous_x_105_wins(self):
        self.assertEqual(pricing.escalate(D(10000), D(9000)), D(10500))

    def test_BR03_current_base_wins(self):
        self.assertEqual(pricing.escalate(D(8000), D(10000)), D(10000))


class TestBR04EarlyRenewal(unittest.TestCase):
    def test_BR04_exactly_60_days_is_8_percent(self):
        self.assertEqual(pricing.early_pct(60), D("0.08"))

    def test_BR04_59_days_is_5_percent(self):
        self.assertEqual(pricing.early_pct(59), D("0.05"))

    def test_BR04_exactly_30_days_is_5_percent(self):
        self.assertEqual(pricing.early_pct(30), D("0.05"))

    def test_BR04_29_days_is_zero(self):
        self.assertEqual(pricing.early_pct(29), D(0))

    def test_BR04_on_end_date_is_zero(self):
        self.assertEqual(pricing.early_pct(0), D(0))


class TestBR05Lapse(unittest.TestCase):
    end = date(2026, 3, 31)

    def test_BR05_first_day_after_end_is_one_month(self):
        self.assertEqual(pricing.lapse_months(self.end, date(2026, 4, 1)), 1)

    def test_BR05_exactly_one_month_is_one(self):
        self.assertEqual(pricing.lapse_months(self.end, date(2026, 4, 30)), 1)

    def test_BR05_part_month_counts_as_full(self):
        self.assertEqual(pricing.lapse_months(self.end, date(2026, 5, 1)), 2)

    def test_BR05_exactly_6_months(self):
        self.assertEqual(pricing.lapse_months(self.end, date(2026, 9, 30)), 6)

    def test_BR05_6_months_and_a_day_is_7(self):
        self.assertEqual(pricing.lapse_months(self.end, date(2026, 10, 1)), 7)

    def test_BR05_two_percent_per_month(self):
        self.assertEqual(pricing.lapse_charge_pct(3), D("0.06"))

    def test_BR05_capped_at_20_percent(self):
        self.assertEqual(pricing.lapse_charge_pct(10), D("0.20"))
        self.assertEqual(pricing.lapse_charge_pct(15), D("0.20"))

    def test_BR05_add_months_clamps_month_end(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))


class TestBR06Inspection(unittest.TestCase):
    def test_BR06_exactly_6_months_no_fee(self):
        self.assertEqual(pricing.inspection_fee(6), D(0))

    def test_BR06_over_6_months_fee_2000(self):
        self.assertEqual(pricing.inspection_fee(7), D(2000))


class TestBR10GstRounding(unittest.TestCase):
    def test_BR10_gst_18_percent(self):
        self.assertEqual(pricing.gst_round(D(10000)), D(11800))

    def test_BR10_rounds_half_up_not_bankers(self):
        self.assertEqual(pricing.gst_round(D(75)), D(89))      # 88.5 -> 89

    def test_BR10_rounds_down_below_half(self):
        self.assertEqual(pricing.gst_round(D("9660")), D(11399))  # 11398.8 -> 11399


if __name__ == "__main__":
    unittest.main()
