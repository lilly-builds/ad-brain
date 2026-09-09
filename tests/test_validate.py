import unittest

from adbrain import validate


class TestLengthGate(unittest.TestCase):
    def test_over_limit_is_blocking_and_states_the_overage(self):
        result = validate.check_line("x" * 40, "google_rsa", "headline")
        self.assertFalse(result.ok)
        length = [v for v in result.violations if v.kind == "length"][0]
        self.assertEqual(length.overage, 10)
        self.assertTrue(length.blocking)

    def test_never_suggests_truncating(self):
        result = validate.check_line("x" * 40, "google_rsa", "headline")
        message = [v for v in result.violations if v.kind == "length"][0].message
        self.assertIn("do not trim", message.lower())

    def test_exactly_at_limit_passes(self):
        self.assertTrue(validate.check_line("x" * 30, "google_rsa", "headline").ok)


class TestCaseRule(unittest.TestCase):
    def test_any_mode_allows_capitals(self):
        rules = {"case": {"rule": "any"}}
        self.assertEqual(validate._check_case("Your Front Desk", rules), [])

    def test_lowercase_mode_rejects_capitals(self):
        rules = {"case": {"rule": "lowercase", "severity": "error", "allow_capitalized": []}}
        found = validate._check_case("Your Front Desk", rules)
        self.assertEqual(len(found), 1)
        self.assertIn("Your", found[0].message)

    def test_lowercase_mode_honours_the_allow_list(self):
        rules = {
            "case": {"rule": "lowercase", "severity": "error",
                     "allow_capitalized": ["Jane App"]},
        }
        self.assertEqual(validate._check_case("switch from Jane App today", rules), [])

    def test_allow_list_prefers_the_longest_match(self):
        # "Jane App" must be consumed whole, not leave a bare "App" behind.
        rules = {"case": {"rule": "lowercase", "severity": "error",
                          "allow_capitalized": ["Jane", "Jane App"]}}
        self.assertEqual(validate._check_case("Jane App works", rules), [])

    def test_sentence_mode_rejects_shouting_only(self):
        rules = {"case": {"rule": "sentence", "severity": "error", "allow_capitalized": []}}
        self.assertEqual(validate._check_case("Your Front Desk", rules), [])
        self.assertEqual(len(validate._check_case("ACT NOW please", rules)), 1)

    def test_unknown_mode_fails_loudly(self):
        with self.assertRaises(ValueError):
            validate._check_case("text", {"case": {"rule": "shouty"}})


class TestVoiceChecks(unittest.TestCase):
    def test_emoji_blocked(self):
        result = validate.check_line("every call answered 🚀", "google_rsa", "headline")
        self.assertFalse(result.ok)
        self.assertTrue(any(v.kind == "emoji" for v in result.violations))

    def test_banned_filler_blocked_with_a_reason(self):
        result = validate.check_line("leverage our platform", "google_rsa", "headline")
        banned = [v for v in result.violations if v.kind == "banned"]
        self.assertTrue(banned)
        self.assertIn("vendor register", banned[0].message)

    def test_unverified_number_warns_but_does_not_block(self):
        result = validate.check_line("we saved teams 47 hours", "google_rsa", "headline")
        claims = [v for v in result.violations if v.kind == "claim"]
        self.assertTrue(claims)
        self.assertFalse(claims[0].blocking)
        self.assertTrue(result.ok)

    def test_allowed_descriptive_numbers_do_not_warn(self):
        result = validate.check_line("answered 24/7", "google_rsa", "headline")
        self.assertEqual([v for v in result.violations if v.kind == "claim"], [])


class TestSetRules(unittest.TestCase):
    def test_too_few_valid_lines_is_blocking(self):
        _, set_level = validate.check_set(["one headline"], "google_rsa", "headline")
        self.assertTrue(any(v.kind == "count" and v.blocking for v in set_level))

    def test_over_limit_lines_do_not_count_toward_the_minimum(self):
        texts = ["fits fine", "also fits", "x" * 90]
        _, set_level = validate.check_set(texts, "google_rsa", "headline")
        self.assertTrue(any("at least 3" in v.message for v in set_level))

    def test_duplicates_flagged(self):
        texts = ["every call answered", "every call answered", "one tool, not five", "book more"]
        _, set_level = validate.check_set(texts, "google_rsa", "headline")
        self.assertTrue(any("appears 2 times" in v.message for v in set_level))

    def test_valid_set_is_clean(self):
        texts = ["every call answered", "one tool, not five", "book more, chase less"]
        results, set_level = validate.check_set(texts, "google_rsa", "headline")
        self.assertTrue(all(r.ok for r in results))
        self.assertEqual(set_level, [])


if __name__ == "__main__":
    unittest.main()
