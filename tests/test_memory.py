import tempfile
import unittest
from pathlib import Path
from unittest import mock

from adbrain import memory


class MemoryTestCase(unittest.TestCase):
    """Each test gets its own memory directory so the real log is untouched."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "experiments").mkdir()
        self._patches = [
            mock.patch.object(memory, "root", lambda: root),
            mock.patch.object(memory, "index_path", lambda: root / "index.jsonl"),
        ]
        for p in self._patches:
            p.start()
        self.root = root

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def make(self, exp_id="run-1", **kwargs):
        defaults = dict(
            id=exp_id, logged_at="2026-09-01T10:00:00", platform="google_rsa",
            angle="contrast with the status quo", hypothesis="framing against manual work lifts ctr",
            campaigns=["search - category"],
        )
        defaults.update(kwargs)
        return memory.Experiment(**defaults)


class TestRoundTrip(MemoryTestCase):
    def test_write_creates_both_representations(self):
        memory.write(self.make())
        self.assertTrue((self.root / "index.jsonl").is_file())
        self.assertTrue((self.root / "experiments" / "run-1.md").is_file())

    def test_markdown_is_readable_by_a_human(self):
        memory.write(self.make())
        text = (self.root / "experiments" / "run-1.md").read_text()
        self.assertIn("## hypothesis", text)
        self.assertIn("framing against manual work lifts ctr", text)

    def test_load_returns_what_was_written(self):
        memory.write(self.make())
        loaded = memory.load_all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].angle, "contrast with the status quo")

    def test_rewriting_the_same_id_replaces_rather_than_duplicates(self):
        memory.write(self.make())
        memory.write(self.make(angle="a different angle"))
        loaded = memory.load_all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].angle, "a different angle")

    def test_a_corrupt_line_does_not_take_down_the_log(self):
        memory.write(self.make("run-1"))
        with (self.root / "index.jsonl").open("a") as fh:
            fh.write("{not valid json\n")
        self.assertEqual(len(memory.load_all()), 1)


class TestOutcomes(MemoryTestCase):
    def test_experiments_start_pending(self):
        memory.write(self.make())
        self.assertEqual(memory.get("run-1").verdict, "pending")

    def test_recording_an_outcome_settles_it(self):
        memory.write(self.make())
        memory.record_outcome("run-1", "won", "it beat the control", {"ctr": 4.9})
        exp = memory.get("run-1")
        self.assertEqual(exp.verdict, "won")
        self.assertEqual(exp.finding, "it beat the control")
        self.assertEqual(exp.outcome["metrics"]["ctr"], 4.9)

    def test_invalid_verdict_is_rejected(self):
        memory.write(self.make())
        with self.assertRaises(ValueError):
            memory.record_outcome("run-1", "kind of good")

    def test_unknown_experiment_names_recent_ids(self):
        memory.write(self.make("run-1"))
        with self.assertRaises(KeyError) as ctx:
            memory.record_outcome("run-99", "won")
        self.assertIn("run-1", str(ctx.exception))

    def test_pending_markdown_tells_you_how_to_close_it(self):
        memory.write(self.make())
        self.assertIn("adbrain outcome", (self.root / "experiments" / "run-1.md").read_text())


class TestRetrieval(MemoryTestCase):
    def test_empty_log_returns_nothing(self):
        self.assertEqual(memory.recall("google_rsa"), [])

    def test_losses_outrank_wins_and_pending(self):
        # Re-testing a lost angle is the most expensive mistake, so it surfaces first.
        memory.write(self.make("won-1", verdict="won", angle="a"))
        memory.write(self.make("pending-1", verdict="pending", angle="b"))
        memory.write(self.make("lost-1", verdict="lost", angle="c"))
        verdicts = [item["verdict"] for item in memory.recall("google_rsa")]
        self.assertEqual(verdicts[0], "lost")
        self.assertEqual(verdicts[-1], "pending")

    def test_same_platform_outranks_another(self):
        memory.write(self.make("meta-1", platform="meta", verdict="won"))
        memory.write(self.make("google-1", platform="google_rsa", verdict="won"))
        self.assertEqual(memory.recall("google_rsa")[0]["run_id"], "google-1")

    def test_matching_campaign_is_weighted_up(self):
        memory.write(self.make("other", campaigns=["search - brand"], verdict="won"))
        memory.write(self.make("match", campaigns=["search - category"], verdict="won"))
        top = memory.recall("google_rsa", campaigns=["search - category"])[0]
        self.assertEqual(top["run_id"], "match")

    def test_limit_is_respected(self):
        for i in range(20):
            memory.write(self.make(f"run-{i}"))
        self.assertEqual(len(memory.recall("google_rsa", limit=5)), 5)

    def test_category_observations_are_retrievable_alongside_owned_tests(self):
        memory.write(self.make("owned-1", verdict="won"))
        memory.write(self.make("cat-1", source="external", angle="competitor is running price framing"))
        sources = {item["source"] for item in memory.recall("google_rsa")}
        self.assertEqual(sources, {"owned", "external"})


class TestLearned(MemoryTestCase):
    def test_empty_log_explains_itself(self):
        self.assertIn("Nothing logged yet", memory.render_learned())

    def test_groups_by_verdict(self):
        memory.write(self.make("w", verdict="won", finding="worked", angle="angle w"))
        memory.write(self.make("l", verdict="lost", finding="failed", angle="angle l"))
        text = memory.render_learned()
        self.assertIn("angles that lost", text)
        self.assertIn("angles that worked", text)
        self.assertIn("do not re-test", text.lower())

    def test_pending_experiments_are_listed_as_unanswered(self):
        memory.write(self.make("p", verdict="pending"))
        self.assertIn("awaiting an outcome", memory.render_learned())

    def test_long_pending_experiments_are_marked_overdue(self):
        memory.write(self.make("old", verdict="pending", logged_at="2020-01-01T10:00:00"))
        self.assertIn("overdue", memory.render_learned())

    def test_external_observations_get_their_own_section(self):
        memory.write(self.make("cat", source="external", angle="price framing appearing"))
        self.assertIn("what the category is doing", memory.render_learned())


class TestFromRun(MemoryTestCase):
    def test_captures_hypothesis_baseline_and_shipped_copy(self):
        brief = {
            "platform": "google_rsa",
            "targets": [{
                "ad_id": "rsa-1", "campaign": "search - brand", "ad_group": "exact",
                "reasons": ["ctr below the account average"],
                "metrics": {"ctr": 1.2, "conversions": 0, "spend": 900.0, "cpa": 0.0,
                            "impressions": 5000, "clicks": 60, "days_live": 40},
            }],
        }
        candidates = [{
            "ad_id": "rsa-1", "campaign": "search - brand",
            "angle": "status quo contrast", "hypothesis": "manual framing will beat feature framing",
            "fields": {"headline": ["one", "two"], "description": ["three"]},
        }]
        exp = memory.from_run("run-x", brief, candidates)
        self.assertEqual(exp.verdict, "pending")
        self.assertEqual(exp.hypothesis, "manual framing will beat feature framing")
        self.assertEqual(exp.variables["lines_generated"], 3)
        self.assertEqual(exp.baseline["rsa-1"]["ctr"], 1.2)
        self.assertIn("ctr below the account average", exp.baseline["rsa-1"]["flagged_for"])


if __name__ == "__main__":
    unittest.main()
