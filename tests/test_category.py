import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adbrain import adlibrary, category


class TestLongevity(unittest.TestCase):
    def test_days_running_uses_the_libraries_start_date(self):
        ad = category.CompetitorAd(ad_id="x", advertiser="A",
                                   started_running="2026-01-01", last_seen="2026-03-02")
        self.assertEqual(ad.days_running(), 60)

    def test_falls_back_to_our_first_observation(self):
        ad = category.CompetitorAd(ad_id="x", advertiser="A",
                                   first_seen="2026-01-01", last_seen="2026-01-31")
        self.assertEqual(ad.days_running(), 30)

    def test_unknown_when_we_have_no_dates_at_all(self):
        ad = category.CompetitorAd(ad_id="x", advertiser="A")
        self.assertIsNone(ad.days_running())
        self.assertEqual(ad.confidence, "unknown")

    def test_confidence_bands(self):
        def conf(days):
            start = dt.date(2026, 1, 1)
            return category.CompetitorAd(
                ad_id="x", advertiser="A",
                started_running=start.isoformat(),
                last_seen=(start + dt.timedelta(days=days)).isoformat(),
            ).confidence
        self.assertEqual(conf(5), "new")
        self.assertEqual(conf(45), "established")
        self.assertEqual(conf(120), "proven")

    def test_synth_id_is_stable_across_whitespace_and_case(self):
        a = category.synth_id("Acme", "Some  Body", "Head")
        b = category.synth_id("Acme", "some body", "head")
        self.assertEqual(a, b)

    def test_synth_id_differs_for_different_creative(self):
        self.assertNotEqual(
            category.synth_id("Acme", "one", "h"),
            category.synth_id("Acme", "two", "h"),
        )


class SnapshotTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "snapshots").mkdir()
        (root / "digests").mkdir()
        self._patches = [
            mock.patch.object(category, "snapshots_dir", lambda: root / "snapshots"),
            mock.patch.object(category, "digests_dir", lambda: root / "digests"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    @staticmethod
    def ad(ad_id, advertiser="Acme", started="", **kw):
        return category.CompetitorAd(ad_id=ad_id, advertiser=advertiser,
                                     headline=f"headline {ad_id}",
                                     started_running=started, **kw)


class TestSnapshots(SnapshotTestCase):
    def test_first_seen_carries_forward_across_snapshots(self):
        # Without this, every snapshot thinks every ad is brand new and
        # longevity never accumulates.
        category.save_snapshot([self.ad("a1")], captured_at="2026-01-01")
        category.save_snapshot([self.ad("a1")], captured_at="2026-03-01")
        _, ads = category.load_snapshot(category.list_snapshots()[-1])
        self.assertEqual(ads[0].first_seen, "2026-01-01")
        self.assertEqual(ads[0].last_seen, "2026-03-01")
        self.assertEqual(ads[0].days_running(), 59)

    def test_snapshots_round_trip(self):
        category.save_snapshot([self.ad("a1", angle="consolidation")], captured_at="2026-01-01")
        _, ads = category.load_snapshot(category.list_snapshots()[0])
        self.assertEqual(ads[0].angle, "consolidation")

    def test_unknown_fields_in_a_snapshot_do_not_break_loading(self):
        path = category.snapshots_dir() / "2026-01-01.json"
        path.write_text(json.dumps({
            "captured_at": "2026-01-01",
            "ads": [{"ad_id": "a", "advertiser": "Acme", "some_future_field": 1}],
        }))
        _, ads = category.load_snapshot(path)
        self.assertEqual(ads[0].advertiser, "Acme")


class TestDiff(SnapshotTestCase):
    def test_first_run_is_a_baseline_not_a_diff(self):
        category.save_snapshot([self.ad("a1")], captured_at="2026-01-01")
        d = category.diff(category.list_snapshots()[0], None)
        self.assertTrue(d.is_first_run)
        self.assertEqual(len(d.launched), 1)
        self.assertIn("First capture", category.render_digest(d))

    def test_detects_launched_killed_and_surviving(self):
        category.save_snapshot([self.ad("a1"), self.ad("a2")], captured_at="2026-01-01")
        category.save_snapshot([self.ad("a2"), self.ad("a3")], captured_at="2026-02-01")
        snaps = category.list_snapshots()
        d = category.diff(snaps[-1], snaps[-2])
        self.assertEqual([a.ad_id for a in d.launched], ["a3"])
        self.assertEqual([a.ad_id for a in d.killed], ["a1"])
        self.assertEqual([a.ad_id for a in d.still_running], ["a2"])

    def test_detects_new_and_departed_advertisers(self):
        category.save_snapshot([self.ad("a1", "Acme")], captured_at="2026-01-01")
        category.save_snapshot([self.ad("b1", "Globex")], captured_at="2026-02-01")
        snaps = category.list_snapshots()
        d = category.diff(snaps[-1], snaps[-2])
        self.assertEqual(d.new_advertisers, ["Globex"])
        self.assertEqual(d.departed_advertisers, ["Acme"])

    def test_killed_ads_are_ordered_longest_running_first(self):
        long_ad = self.ad("old", started="2025-01-01")
        short_ad = self.ad("new", started="2026-01-20")
        category.save_snapshot([long_ad, short_ad], captured_at="2026-02-01")
        category.save_snapshot([], captured_at="2026-03-01")
        snaps = category.list_snapshots()
        d = category.diff(snaps[-1], snaps[-2])
        self.assertEqual([a.ad_id for a in d.killed], ["old", "new"])

    def test_digest_states_longevity_is_a_proxy(self):
        category.save_snapshot([self.ad("a1", started="2025-01-01")], captured_at="2026-01-01")
        category.save_snapshot([self.ad("a1", started="2025-01-01")], captured_at="2026-02-01")
        snaps = category.list_snapshots()
        text = category.render_digest(category.diff(snaps[-1], snaps[-2]))
        self.assertIn("proxy, not a measurement", text)

    def test_cadence_counts_live_creatives_per_advertiser(self):
        category.save_snapshot(
            [self.ad("a1", "Acme"), self.ad("a2", "Acme"), self.ad("b1", "Globex")],
            captured_at="2026-01-01")
        d = category.diff(category.list_snapshots()[0], None)
        self.assertEqual(d.cadence["Acme"], 2)
        self.assertEqual(d.cadence["Globex"], 1)


class TestCoverageHonesty(unittest.TestCase):
    def test_us_queries_are_warned_about(self):
        warning = adlibrary.coverage_warning(["US"])
        self.assertIsNotNone(warning)
        self.assertIn("EU/UK", warning)

    def test_uk_and_eu_queries_are_not_warned_about(self):
        self.assertIsNone(adlibrary.coverage_warning(["GB"]))
        self.assertIsNone(adlibrary.coverage_warning(["DE", "FR"]))

    def test_missing_token_explains_the_manual_path(self):
        with mock.patch.dict("os.environ", {"META_AD_LIBRARY_TOKEN": ""}, clear=False):
            with self.assertRaises(adlibrary.AdLibraryError) as ctx:
                adlibrary.token()
        self.assertIn("--from-file", str(ctx.exception))


class TestManualCapture(unittest.TestCase):
    def write(self, text, suffix=".csv"):
        tmp = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        return tmp.name

    def test_reads_a_capture_sheet(self):
        path = self.write(
            "advertiser,headline,body,started_running,relationship\n"
            "Acme,never miss a call,body text,2026-01-01,direct\n"
        )
        ads = adlibrary.from_file(path)
        self.assertEqual(len(ads), 1)
        self.assertEqual(ads[0].advertiser, "Acme")
        self.assertEqual(ads[0].started_running, "2026-01-01")
        self.assertEqual(ads[0].source, "manual")

    def test_synthesises_an_id_when_none_is_given(self):
        path = self.write("advertiser,headline\nAcme,a headline\n")
        self.assertTrue(adlibrary.from_file(path)[0].ad_id.startswith("syn-"))

    def test_rows_without_advertiser_or_copy_are_skipped(self):
        path = self.write("advertiser,headline\nAcme,good row\n,\n")
        self.assertEqual(len(adlibrary.from_file(path)), 1)

    def test_a_file_with_no_usable_rows_explains_what_is_required(self):
        path = self.write("advertiser,headline\n,\n")
        with self.assertRaises(adlibrary.AdLibraryError) as ctx:
            adlibrary.from_file(path)
        self.assertIn("advertiser", str(ctx.exception))

    def test_reads_json_too(self):
        path = self.write(
            json.dumps({"ads": [{"advertiser": "Acme", "headline": "h", "body": "b"}]}),
            suffix=".json")
        self.assertEqual(adlibrary.from_file(path)[0].advertiser, "Acme")


if __name__ == "__main__":
    unittest.main()
