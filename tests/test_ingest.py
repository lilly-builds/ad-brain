import datetime as dt
import tempfile
import unittest
from pathlib import Path

from adbrain import config, ingest


class TestNumberParsing(unittest.TestCase):
    def test_strips_currency_and_thousands_separators(self):
        self.assertEqual(ingest._to_float("$1,234.56"), 1234.56)
        self.assertEqual(ingest._to_float("12,345"), 12345.0)

    def test_handles_european_decimal_comma(self):
        self.assertEqual(ingest._to_float("1.234,56"), 1234.56)
        self.assertEqual(ingest._to_float("12,50"), 12.5)

    def test_placeholders_become_zero_rather_than_raising(self):
        for blank in ("", "--", "—", "n/a", None):
            self.assertEqual(ingest._to_float(blank), 0.0)

    def test_percentages(self):
        self.assertEqual(ingest._to_float("3.45%"), 3.45)


class TestFixtureParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = config.repo_root()
        cls.ads = ingest.read(root / "data/fixtures/google_rsa_sample.csv", "google_rsa")
        cls.meta = ingest.read(root / "data/fixtures/meta_sample.csv", "meta")

    def test_skips_report_title_rows_and_the_total_row(self):
        # The fixture has two title lines before the header and a Total row after.
        self.assertEqual(len(self.ads), 45)
        self.assertFalse(any(a.ad_id.lower().startswith("total") for a in self.ads))

    def test_collapses_numbered_columns_into_one_field(self):
        ad = self.ads[0]
        self.assertEqual(len(ad.texts("headline")), 6)
        self.assertEqual(len(ad.texts("description")), 2)

    def test_reads_performance_columns(self):
        ad = self.ads[0]
        self.assertGreater(ad.metrics.impressions, 0)
        self.assertGreater(ad.metrics.spend, 0)

    def test_derives_days_live_from_a_start_date(self):
        self.assertTrue(all(a.metrics.days_live_known for a in self.ads))
        self.assertTrue(all(a.metrics.days_live >= 0 for a in self.ads))

    def test_meta_aliases_map_onto_our_field_names(self):
        ad = self.meta[0]
        self.assertTrue(ad.texts("primary_text"))
        self.assertTrue(ad.texts("headline"))
        self.assertGreater(ad.metrics.clicks, 0)


class TestMissingStartDate(unittest.TestCase):
    def test_absent_dates_mark_age_unknown_rather_than_zero(self):
        # An export with no start date must not make every ad look brand new,
        # or the significance gate would exclude the entire file.
        csv = (
            "Campaign,Ad group,Ad ID,Headline 1,Headline 2,Headline 3,"
            "Description 1,Description 2,Impressions,Clicks,Conversions,Cost\n"
            "c,g,a-1,one,two,three,desc one,desc two,5000,100,4,500.00\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "no_dates.csv"
            path.write_text(csv, encoding="utf-8")
            ads = ingest.read(path, "google_rsa")
        self.assertEqual(len(ads), 1)
        self.assertFalse(ads[0].metrics.days_live_known)
        self.assertEqual(ads[0].metrics.days_live, 0.0)

    def test_explicit_days_live_column_is_used_when_present(self):
        csv = (
            "Campaign,Ad group,Ad ID,Headline 1,Headline 2,Headline 3,"
            "Impressions,Clicks,Days live\n"
            "c,g,a-1,one,two,three,5000,100,42\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "days.csv"
            path.write_text(csv, encoding="utf-8")
            ads = ingest.read(path, "google_rsa")
        self.assertTrue(ads[0].metrics.days_live_known)
        self.assertEqual(ads[0].metrics.days_live, 42.0)


class TestUnsupportedPlatform(unittest.TestCase):
    def test_error_distinguishes_registered_limits_from_available_parsers(self):
        with self.assertRaises(KeyError) as ctx:
            ingest.read("whatever.csv", "linkedin")
        self.assertIn("google_rsa", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
