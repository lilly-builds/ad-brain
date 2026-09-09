import unittest

from adbrain import rank
from adbrain.models import Ad, Metrics


def make_ad(ad_id="a", impressions=5000, clicks=100, conversions=5, spend=500.0,
            days=30.0, days_known=True):
    return Ad(
        ad_id=ad_id, platform="google_rsa",
        fields={"headline": ["one", "two", "three"]},
        metrics=Metrics(impressions=impressions, clicks=clicks, conversions=conversions,
                        spend=spend, days_live=days, days_live_known=days_known),
    )


GATE = {"significance": {"min_impressions": 500, "min_days_live": 7}}


class TestSignificanceGate(unittest.TestCase):
    def test_low_impression_ads_are_never_flagged(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "any_ctr", "plain_english": "ctr below 50%", "severity": "high",
            "conditions": [{"metric": "ctr", "compare": "absolute", "operator": "<", "value": 50.0}],
        }]
        judged, _ = rank.judge([make_ad(impressions=100, clicks=1)], cfg)
        self.assertFalse(judged[0].significant)
        self.assertEqual(judged[0].flags, [])

    def test_young_ads_are_never_flagged(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "any_ctr", "plain_english": "ctr below 50%", "severity": "high",
            "conditions": [{"metric": "ctr", "compare": "absolute", "operator": "<", "value": 50.0}],
        }]
        judged, _ = rank.judge([make_ad(days=2)], cfg)
        self.assertFalse(judged[0].significant)

    def test_unknown_age_skips_the_age_check_rather_than_excluding_everything(self):
        cfg = dict(GATE)
        cfg["rules"] = []
        judged, cohort = rank.judge([make_ad(days=0.0, days_known=False)], cfg)
        self.assertTrue(judged[0].significant)
        self.assertTrue(cohort.age_unknown)


class TestComparisons(unittest.TestCase):
    def test_percentile_reads_as_share_below(self):
        self.assertEqual(rank._percentile(5, [1, 2, 3, 4, 5]), 80.0)
        self.assertEqual(rank._percentile(1, [1, 2, 3, 4, 5]), 0.0)

    def test_percentile_of_empty_population_is_neutral(self):
        self.assertEqual(rank._percentile(5, []), 50.0)

    def test_ratio_to_account_mean(self):
        ads = [make_ad("a", clicks=100), make_ad("b", clicks=300)]  # ctr 2% and 6%, mean 4%
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "half_the_average", "plain_english": "below half the average", "severity": "high",
            "conditions": [{"metric": "ctr", "compare": "ratio_to_account_mean",
                            "operator": "<", "value": 0.6}],
        }]
        judged, _ = rank.judge(ads, cfg)
        flagged = {j.ad.ad_id for j in judged if j.is_underperformer}
        self.assertEqual(flagged, {"a"})

    def test_unknown_compare_mode_fails_loudly(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "bad", "plain_english": "x", "severity": "high",
            "conditions": [{"metric": "ctr", "compare": "vibes", "operator": "<", "value": 1}],
        }]
        with self.assertRaises(ValueError):
            rank.judge([make_ad()], cfg)


class TestRuleSemantics(unittest.TestCase):
    def test_all_conditions_in_a_rule_must_match(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "spend_no_conversions", "plain_english": "spent with nothing to show",
            "severity": "high",
            "conditions": [
                {"metric": "spend", "compare": "absolute", "operator": ">", "value": 100.0},
                {"metric": "conversions", "compare": "absolute", "operator": "==", "value": 0.0},
            ],
        }]
        spent_and_converted = make_ad("converted", spend=500.0, conversions=5)
        spent_and_nothing = make_ad("nothing", spend=500.0, conversions=0)
        judged, _ = rank.judge([spent_and_converted, spent_and_nothing], cfg)
        flagged = {j.ad.ad_id for j in judged if j.is_underperformer}
        self.assertEqual(flagged, {"nothing"})

    def test_winners_are_never_flagged(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "old", "plain_english": "running a long time", "severity": "low",
            "conditions": [{"metric": "days_live", "compare": "absolute", "operator": ">", "value": 10.0}],
        }]
        cfg["winners"] = [{
            "name": "converts", "plain_english": "converts well",
            "conditions": [{"metric": "conversions", "compare": "absolute", "operator": ">=", "value": 3.0}],
        }]
        judged, _ = rank.judge([make_ad(conversions=10, days=200)], cfg)
        self.assertTrue(judged[0].is_winner)
        self.assertFalse(judged[0].is_underperformer)

    def test_flags_carry_the_plain_english_reason_and_evidence(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "expensive", "plain_english": "costs more than we want to pay",
            "severity": "high",
            "conditions": [{"metric": "cpa", "compare": "absolute", "operator": ">", "value": 10.0}],
        }]
        judged, _ = rank.judge([make_ad(spend=1000.0, conversions=1)], cfg)
        flag = judged[0].flags[0]
        self.assertEqual(flag.plain_english, "costs more than we want to pay")
        self.assertTrue(flag.evidence)
        self.assertIn("cpa", flag.evidence[0])


class TestSummary(unittest.TestCase):
    def test_counts_and_wasted_spend(self):
        cfg = dict(GATE)
        cfg["rules"] = [{
            "name": "no_conv", "plain_english": "no conversions", "severity": "high",
            "conditions": [{"metric": "conversions", "compare": "absolute", "operator": "==", "value": 0.0}],
        }]
        ads = [make_ad("a", conversions=0, spend=300.0), make_ad("b", conversions=5, spend=200.0)]
        judged, cohort = rank.judge(ads, cfg)
        summary = rank.summarise(judged, cohort)
        self.assertEqual(summary["flagged"], 1)
        self.assertEqual(summary["wasted_spend"], 300.0)
        self.assertEqual(summary["total_ads"], 2)


if __name__ == "__main__":
    unittest.main()
