import unittest

from adbrain import platforms


class TestPlatforms(unittest.TestCase):
    def test_limits_load_from_config(self):
        spec = platforms.get("google_rsa")
        self.assertEqual(spec.field("headline").limit, 30)
        self.assertEqual(spec.field("description").limit, 90)
        self.assertEqual(spec.field("headline").max_count, 15)

    def test_meta_records_api_max_separately_from_display_limit(self):
        # We gate on the display limit; the true API max is kept for reference.
        primary = platforms.get("meta").field("primary_text")
        self.assertEqual(primary.limit, 125)
        self.assertEqual(primary.hard_max, 2200)

    def test_counts_composed_characters_as_one(self):
        # "cafe" + combining acute is 5 code points but 4 characters to a platform.
        self.assertEqual(platforms.count_chars("café"), 4)
        self.assertEqual(platforms.count_chars("café"), 4)

    def test_overage_reports_how_far_over(self):
        spec = platforms.get("google_rsa").field("headline")
        self.assertEqual(spec.overage("x" * 34), 4)
        self.assertLessEqual(spec.overage("x" * 30), 0)

    def test_unknown_platform_names_the_alternatives(self):
        with self.assertRaises(KeyError) as ctx:
            platforms.get("myspace")
        self.assertIn("google_rsa", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
