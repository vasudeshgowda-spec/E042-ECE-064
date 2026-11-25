"""Integration tests through Engine.process: BR-01..BR-11, validation and the five mandatory edge cases."""
import unittest
from datetime import date
from decimal import Decimal as D

from amc.dates import add_years
from tests.helpers import cmd, make_engine, one


class TestRenewPipeline(unittest.TestCase):
    def test_BR03_BR04_BR10_renew_60_days_early_full_pipeline(self):
        e = one()
        r = e.process([cmd(0, "RENEW", "K1", date(2026, 11, 1))])
        q = r.quotations[0]
        self.assertEqual((q.new_start, q.new_end), (date(2027, 1, 1), date(2027, 12, 31)))
        self.assertEqual(q.escalated, D(10500))
        self.assertEqual(q.early_pct, D("0.08"))
        self.assertEqual(q.final, D(11399))

    def test_BR04_edge_renew_exactly_30_days_before_end(self):
        r = one().process([cmd(0, "RENEW", "K1", date(2026, 12, 1))])
        self.assertEqual(r.quotations[0].early_pct, D("0.05"))
        self.assertEqual(r.quotations[0].final, D(11771))          # 10500*0.95*1.18 = 11770.5 -> 11771

    def test_BR04_edge_renew_exactly_60_days_before_end(self):
        r = one().process([cmd(0, "RENEW", "K1", date(2026, 11, 1))])
        self.assertEqual(r.quotations[0].early_pct, D("0.08"))

    def test_BR03_renewal_updates_last_annual_value(self):
        e = one()
        e.process([cmd(0, "RENEW", "K1", date(2026, 12, 31))])
        self.assertEqual(e.contracts["K1"].last_annual_value, D(10500))

    def test_BR02_edge_age_exactly_8_at_new_term_start_no_surcharge(self):
        install = add_years(date(2027, 1, 1), -8)
        q = one(install=install).process([cmd(0, "RENEW", "K1", date(2026, 12, 31))]).quotations[0]
        self.assertFalse(q.age_surcharge)
        self.assertEqual(q.final, D(12390))

    def test_BR02_edge_older_than_8_at_new_term_start_surcharge_applies(self):
        install = date(2026, 12, 31).replace(year=2018)            # 8y + 1 day before 2027-01-01
        q = one(install=install).process([cmd(0, "RENEW", "K1", date(2026, 12, 31))]).quotations[0]
        self.assertTrue(q.age_surcharge)
        self.assertEqual(q.escalated, D(12500))
        self.assertEqual(q.final, D(14750))

    def test_BR02_edge_equipment_turning_8_during_new_term(self):
        install = date(2019, 3, 1)                                 # turns 8 on 2027-03-01, inside 2027 term
        q = one(install=install).process([cmd(0, "RENEW", "K1", date(2026, 12, 31))]).quotations[0]
        self.assertFalse(q.age_surcharge)


class TestLapse(unittest.TestCase):
    def setUp(self):
        self.e = one("BASIC", start=date(2025, 4, 1), end=date(2026, 3, 31), last=5000)

    def test_BR05_BR06_lapse_7_months_charge_and_inspection(self):
        q = self.e.process([cmd(0, "RENEW", "K1", date(2026, 10, 1))]).quotations[0]
        self.assertEqual(q.new_start, date(2026, 10, 1))
        self.assertEqual(q.new_end, date(2027, 9, 30))
        self.assertEqual((q.lapse_months, q.lapse_pct), (7, D("0.14")))
        self.assertEqual(q.inspection_fee, D(2000))
        self.assertEqual(q.final, D(10431))                        # (6000+840+2000)*1.18 = 10431.2

    def test_BR06_edge_lapse_exactly_6_months_no_inspection(self):
        q = self.e.process([cmd(0, "RENEW", "K1", date(2026, 9, 30))]).quotations[0]
        self.assertEqual(q.lapse_months, 6)
        self.assertEqual(q.inspection_fee, D(0))
        self.assertEqual(q.final, D(7930))                         # 6720*1.18 = 7929.6

    def test_BR05_lapse_charge_capped_at_20_percent(self):
        q = self.e.process([cmd(0, "RENEW", "K1", date(2027, 3, 31))]).quotations[0]
        self.assertEqual(q.lapse_pct, D("0.20"))

    def test_BR05_no_early_discount_on_a_lapsed_renewal(self):
        q = self.e.process([cmd(0, "RENEW", "K1", date(2026, 4, 10))]).quotations[0]
        self.assertEqual(q.early_pct, D(0))

    def test_BR11_lapse_command_marks_contract_lapsed_then_renew_reactivates(self):
        r = self.e.process([cmd(0, "LAPSE", "K1", date(2026, 4, 15)), cmd(1, "RENEW", "K1", date(2026, 5, 1))])
        self.assertEqual(len(r.quotations), 1)
        self.assertEqual(self.e.contracts["K1"].status, "ACTIVE")


class TestUpgradeDowngrade(unittest.TestCase):
    def test_BR07_upgrade_mid_term_prorated(self):
        e = one("BASIC", last=6000)
        r = e.process([cmd(0, "UPGRADE", "K1", date(2026, 7, 1), "PREMIUM")])
        u = r.upgrades[0]
        self.assertEqual((u.remaining_days, u.term_days), (184, 365))
        self.assertEqual(u.final, D(4759))                         # 8000*184/365*1.18
        self.assertEqual(e.contracts["K1"].coverage, "PREMIUM")

    def test_BR07_edge_upgrade_on_last_day_of_term_charges_one_day(self):
        u = one("BASIC", last=6000).process([cmd(0, "UPGRADE", "K1", date(2026, 12, 31), "PREMIUM")]).upgrades[0]
        self.assertEqual(u.remaining_days, 1)
        self.assertEqual(u.final, D(26))                           # 8000/365*1.18 = 25.86

    def test_BR07_upgrade_on_first_day_charges_full_difference(self):
        u = one("BASIC", last=6000).process([cmd(0, "UPGRADE", "K1", date(2026, 1, 1), "PREMIUM")]).upgrades[0]
        self.assertEqual(u.final, D(9440))                         # 8000*1.18

    def test_BR08_downgrade_changes_nothing_now(self):
        e = one("PREMIUM", last=14000)
        r = e.process([cmd(0, "DOWNGRADE", "K1", date(2026, 3, 1), "BASIC")])
        self.assertEqual(e.contracts["K1"].coverage, "PREMIUM")
        self.assertEqual(e.contracts["K1"].pending_coverage, "BASIC")
        self.assertEqual((r.upgrades, r.quotations, r.rejections), ([], [], []))

    def test_BR03_BR08_downgrade_applies_at_renewal_and_floor_protects_price(self):
        e = one("PREMIUM", last=14000)
        q = e.process([cmd(0, "DOWNGRADE", "K1", date(2026, 3, 1), "BASIC"),
                       cmd(1, "RENEW", "K1", date(2026, 11, 1))]).quotations[0]
        self.assertEqual(q.coverage, "BASIC")
        self.assertEqual(q.base, D(6000))
        self.assertEqual(q.escalated, D(14700))                    # floor: 14000 x 1.05, not 6000
        self.assertEqual(q.final, D(15958))                        # 14700*0.92*1.18 = 15958.32
        self.assertEqual(e.contracts["K1"].coverage, "BASIC")
        self.assertIsNone(e.contracts["K1"].pending_coverage)

    def test_BR08_upgrade_cancels_pending_downgrade(self):
        e = one("PREMIUM", last=14000)
        e.contracts["K1"].coverage = "COMPREHENSIVE"
        e.process([cmd(0, "DOWNGRADE", "K1", date(2026, 3, 1), "BASIC"), cmd(1, "UPGRADE", "K1", date(2026, 4, 1), "PREMIUM")])
        self.assertIsNone(e.contracts["K1"].pending_coverage)


class TestBR09MultiEquipment(unittest.TestCase):
    @staticmethod
    def engine(dates):
        contracts = [(f"K{i}", "COMPREHENSIVE", add_years(d, -1), d, 10000) for i, d in enumerate(dates)]
        return make_engine(contracts)

    def renew_all(self, dates):
        e = self.engine(dates)
        return e.process([cmd(i, "RENEW", f"K{i}", d) for i, d in enumerate(dates)]).quotations

    def test_BR09_five_renewals_same_month_all_get_3_percent(self):
        qs = self.renew_all([date(2026, 5, d) for d in (4, 11, 19, 26, 31)])
        self.assertTrue(all(q.multi_pct == D("0.03") for q in qs))
        self.assertTrue(all(q.final == D(12018) for q in qs))      # 10500*0.97*1.18 = 12018.3

    def test_BR09_edge_fifth_renewal_on_the_31st_discounts_the_earlier_four_too(self):
        qs = self.renew_all([date(2026, 5, d) for d in (4, 11, 19, 26, 31)])
        self.assertEqual(qs[0].multi_pct, D("0.03"))
        self.assertEqual(qs[3].multi_pct, D("0.03"))

    def test_BR09_four_renewals_no_discount(self):
        qs = self.renew_all([date(2026, 5, d) for d in (4, 11, 19, 26)])
        self.assertTrue(all(q.multi_pct == 0 for q in qs))
        self.assertTrue(all(q.final == D(12390) for q in qs))

    def test_BR09_renewals_split_across_months_do_not_combine(self):
        qs = self.renew_all([date(2026, 5, 4), date(2026, 5, 11), date(2026, 5, 19), date(2026, 5, 31), date(2026, 6, 1)])
        self.assertTrue(all(q.multi_pct == 0 for q in qs))

    def test_BR09_other_customers_renewals_do_not_count(self):
        e = self.engine([date(2026, 5, d) for d in (4, 11, 19, 26, 31)])
        e.equipment["E4"] = e.equipment["E4"].__class__("E4", "C2", "x", e.equipment["E4"].list_price, e.equipment["E4"].install_date)
        qs = e.process([cmd(i, "RENEW", f"K{i}", d) for i, d in enumerate([date(2026, 5, x) for x in (4, 11, 19, 26, 31)])]).quotations
        self.assertTrue(all(q.multi_pct == 0 for q in qs))


class TestValidationAndStatus(unittest.TestCase):
    def reasons(self, commands, engine=None):
        return [r.reason for r in (engine or one()).process(commands).rejections]

    def test_VR01_unknown_contract_rejected(self):
        self.assertIn("unknown contract", self.reasons([cmd(0, "RENEW", "NOPE", date(2026, 5, 1))]))

    def test_VR02_unknown_command_type_rejected(self):
        self.assertTrue(self.reasons([cmd(0, "CANCEL", "K1", date(2026, 5, 1))])[0].startswith("unknown command"))

    def test_VR04_upgrade_to_same_level_rejected(self):
        self.assertEqual(len(self.reasons([cmd(0, "UPGRADE", "K1", date(2026, 5, 1), "COMPREHENSIVE")])), 1)

    def test_VR04_downgrade_to_higher_level_rejected(self):
        self.assertEqual(len(self.reasons([cmd(0, "DOWNGRADE", "K1", date(2026, 5, 1), "PREMIUM")])), 1)

    def test_VR05_upgrade_on_lapsed_contract_rejected(self):
        self.assertEqual(len(self.reasons([cmd(0, "UPGRADE", "K1", date(2027, 2, 1), "PREMIUM")])), 1)

    def test_VR06_renew_before_term_start_rejected(self):
        self.assertEqual(len(self.reasons([cmd(0, "RENEW", "K1", date(2025, 12, 31))])), 1)

    def test_VR06_second_renew_for_same_cycle_rejected(self):
        r = self.reasons([cmd(0, "RENEW", "K1", date(2026, 11, 1)), cmd(1, "RENEW", "K1", date(2026, 11, 5))])
        self.assertEqual(len(r), 1)

    def test_VR07_commands_processed_in_date_order_not_file_order(self):
        e = one("PREMIUM", last=14000)
        r = e.process([cmd(0, "RENEW", "K1", date(2026, 11, 1)), cmd(1, "DOWNGRADE", "K1", date(2026, 3, 1), "BASIC")])
        self.assertEqual(r.quotations[0].coverage, "BASIC")

    def test_BR11_status_active_pending_and_lapsed(self):
        e = one("PREMIUM", last=14000)
        c = e.contracts["K1"]
        self.assertEqual(e.status(c, date(2026, 6, 1)), "ACTIVE")
        c.pending_coverage = "BASIC"
        self.assertEqual(e.status(c, date(2026, 6, 1)), "ACTIVE (DOWNGRADE PENDING)")
        self.assertEqual(e.status(c, date(2027, 1, 1)), "LAPSED")


if __name__ == "__main__":
    unittest.main()
