import importlib.util
import unittest
from pathlib import Path

import yaml

from scripts.experiments.forecast_collection_plan import (
    build_plan,
    load_config,
)
from src.twin.forecasting.continuity import assign_segments
from src.twin.forecasting.splitter import (
    DEFAULT_SPLIT_POLICY,
    SPLIT_NAMES,
    SplitAssignment,
    SplitPolicy,
    assert_no_leakage,
    assign_split,
    build_run_id,
    parse_run_id,
    split_frame,
    split_rows,
    split_run_ids,
)

# pandas is optional; the dummy rows used by most tests do not need it.
HAS_PANDAS = importlib.util.find_spec("pandas") is not None

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "experiments" / "forecast_dataset_2c20s.yaml"
SEEN = ("stable", "gradual", "burst", "oscillating")
SEEDS = (101, 102, 103, 104, 105)


def official_run_ids() -> list[str]:
    """The 25 official run ids: 5 workloads x 5 repeats."""
    return [
        build_run_id(workload, repeat, SEEDS[repeat - 1])
        for workload in (*SEEN, "hot-switch")
        for repeat in range(1, 6)
    ]


def dummy_rows(run_ids: list[str], samples: int = 6) -> list[dict[str, object]]:
    """Dummy dataframe: two controllers, a 5 s hole in each series."""
    rows: list[dict[str, object]] = []

    for run_id in run_ids:
        for controller_id in ("c1", "c2"):
            timestamps = [0, 1, 2, 8, 9, 10][:samples]
            segments = assign_segments(timestamps, 2.5)
            for second, segment in zip(timestamps, segments):
                rows.append(
                    {
                        "run_id": run_id,
                        "controller_id": controller_id,
                        "t": second,
                        "segment_id": segment,
                        "utilization": 0.5,
                    }
                )

    return rows


class ForecastSplitTests(unittest.TestCase):
    def setUp(self):
        self.assignment = split_run_ids(official_run_ids())
        self.train = set(self.assignment.train)
        self.validation = set(self.assignment.validation)
        self.test = set(self.assignment.test)
        self.unseen = set(self.assignment.unseen)

    # ---- sizes of the frozen strategy -----------------------------------

    def test_split_sizes(self):
        self.assertEqual(len(self.train), 12)
        self.assertEqual(len(self.validation), 4)
        self.assertEqual(len(self.test), 4)
        self.assertEqual(len(self.unseen), 5)
        self.assertEqual(
            len(self.train | self.validation | self.test | self.unseen),
            25,
        )

    def test_repeat_mapping_for_every_seen_workload(self):
        for workload in SEEN:
            with self.subTest(workload=workload):
                for repeat in (1, 2, 3):
                    run_id = build_run_id(workload, repeat, SEEDS[repeat - 1])
                    self.assertEqual(assign_split(run_id), "train")
                self.assertEqual(
                    assign_split(build_run_id(workload, 4, 104)),
                    "validation",
                )
                self.assertEqual(
                    assign_split(build_run_id(workload, 5, 105)),
                    "test",
                )

    def test_every_hot_switch_repeat_is_unseen(self):
        for repeat in range(1, 6):
            run_id = build_run_id("hot-switch", repeat, SEEDS[repeat - 1])
            self.assertEqual(assign_split(run_id), "unseen")

    # ---- pairwise disjointness (data leakage guards) ---------------------

    def test_train_validation_disjoint(self):
        self.assertEqual(self.train & self.validation, set())

    def test_train_test_disjoint(self):
        self.assertEqual(self.train & self.test, set())

    def test_validation_test_disjoint(self):
        self.assertEqual(self.validation & self.test, set())

    def test_unseen_train_disjoint(self):
        self.assertEqual(self.unseen & self.train, set())

    def test_unseen_validation_disjoint(self):
        self.assertEqual(self.unseen & self.validation, set())

    def test_unseen_test_disjoint(self):
        self.assertEqual(self.unseen & self.test, set())

    def test_hot_switch_not_in_train_validation_test(self):
        seen_runs = self.train | self.validation | self.test

        self.assertTrue(all(run.startswith("hot-switch-") for run in self.unseen))
        self.assertFalse(any(run.startswith("hot-switch-") for run in seen_runs))

    def test_same_run_id_cannot_appear_in_two_splits(self):
        leaky = SplitAssignment(
            train=("stable-r01-s101",),
            validation=("stable-r01-s101",),
            test=(),
            unseen=(),
        )

        with self.assertRaises(ValueError):
            assert_no_leakage(leaky)

        # A hot-switch run placed in test is rejected the same way.
        leaky_unseen = SplitAssignment(
            train=(),
            validation=(),
            test=("hot-switch-r01-s101",),
            unseen=("hot-switch-r01-s101",),
        )
        with self.assertRaises(ValueError):
            assert_no_leakage(leaky_unseen)

    def test_each_run_id_belongs_to_exactly_one_split(self):
        for run_id in official_run_ids():
            owners = [
                name
                for name, members in self.assignment.as_dict().items()
                if run_id in members
            ]
            self.assertEqual(len(owners), 1, run_id)

    # ---- random_shuffle == false ----------------------------------------

    def test_random_shuffle_is_false(self):
        self.assertFalse(DEFAULT_SPLIT_POLICY.random_shuffle)

    def test_random_shuffle_cannot_be_enabled(self):
        with self.assertRaises(ValueError):
            SplitPolicy(random_shuffle=True)

    def test_split_is_deterministic_and_independent_of_input_order(self):
        forward = split_run_ids(official_run_ids())
        backward = split_run_ids(list(reversed(official_run_ids())))

        self.assertEqual(forward, backward)

    def test_rows_keep_original_order(self):
        rows = dummy_rows(["stable-r01-s101", "stable-r02-s102"])
        result = split_rows(rows)

        self.assertEqual(result["train"], rows)

    # ---- cross-run / cross-sequence leakage -----------------------------

    def test_rows_of_one_run_never_span_two_splits(self):
        rows = dummy_rows(official_run_ids())
        result = split_rows(rows)

        split_of_run: dict[object, str] = {}
        for name, members in result.items():
            for row in members:
                previous = split_of_run.setdefault(row["run_id"], name)
                self.assertEqual(previous, name, row["run_id"])

        self.assertEqual(
            sum(len(members) for members in result.values()),
            len(rows),
        )

    def test_no_continuity_segment_spans_two_splits(self):
        rows = dummy_rows(official_run_ids())
        result = split_rows(rows)

        owner: dict[tuple[object, object, object], str] = {}
        for name, members in result.items():
            for row in members:
                key = (row["run_id"], row["controller_id"], row["segment_id"])
                self.assertEqual(owner.setdefault(key, name), name, key)

    def test_unseen_rows_contain_only_hot_switch(self):
        result = split_rows(dummy_rows(official_run_ids()))

        self.assertTrue(result["unseen"])
        self.assertTrue(
            all(
                str(row["run_id"]).startswith("hot-switch-")
                for row in result["unseen"]
            )
        )
        for name in ("train", "validation", "test"):
            self.assertFalse(
                any(
                    str(row["run_id"]).startswith("hot-switch-")
                    for row in result[name]
                )
            )

    @unittest.skipUnless(HAS_PANDAS, "pandas is not installed")
    def test_dataframe_split(self):
        import pandas

        frame = pandas.DataFrame(dummy_rows(official_run_ids()))
        parts = split_frame(frame)

        self.assertEqual(set(parts), set(SPLIT_NAMES))
        self.assertEqual(sum(len(part) for part in parts.values()), len(frame))
        self.assertTrue(
            set(parts["train"]["run_id"]).isdisjoint(parts["test"]["run_id"])
        )
        self.assertTrue(
            parts["train"].index.is_monotonic_increasing
        )

    # ---- run id contract -------------------------------------------------

    def test_parse_run_id_with_hyphenated_workload(self):
        parsed = parse_run_id("hot-switch-r05-s105")

        self.assertEqual(
            (parsed.workload, parsed.repeat, parsed.seed),
            ("hot-switch", 5, 105),
        )

    def test_build_and_parse_round_trip(self):
        for run_id in official_run_ids():
            parsed = parse_run_id(run_id)
            self.assertEqual(
                build_run_id(parsed.workload, parsed.repeat, parsed.seed),
                run_id,
            )

    def test_invalid_run_ids_are_rejected(self):
        for run_id in (
            "",
            "stable",
            "stable-r1-s101",
            "Stable-r01-s101",
            "stable-r01",
            "forecast-stable-2c20s-r01",
        ):
            with self.subTest(run_id=run_id):
                with self.assertRaises(ValueError):
                    parse_run_id(run_id)

    def test_unknown_workload_or_repeat_is_rejected_not_dropped(self):
        with self.assertRaises(ValueError):
            assign_split("mystery-r01-s101")

        with self.assertRaises(ValueError):
            assign_split("stable-r06-s106")

    def test_policy_rejects_overlapping_repeats(self):
        with self.assertRaises(ValueError):
            SplitPolicy(train_repeats=(1, 2, 4), validation_repeats=(4,))

    def test_policy_rejects_workload_both_seen_and_unseen(self):
        with self.assertRaises(ValueError):
            SplitPolicy(unseen_workloads=("stable",))

    # ---- agreement with the real experiment plan ------------------------

    def test_official_plan_run_ids_follow_the_contract_and_split_12_4_4_5(self):
        config = load_config(CONFIG_PATH)
        plan = build_plan(config)
        assignment = split_run_ids(run.run_id for run in plan)

        self.assertEqual(len(plan), 25)
        self.assertEqual(
            (
                len(assignment.train),
                len(assignment.validation),
                len(assignment.test),
                len(assignment.unseen),
            ),
            (12, 4, 4, 5),
        )

        for run in plan:
            parsed = parse_run_id(run.run_id)
            self.assertEqual(parsed.workload, run.workload)
            self.assertEqual(parsed.repeat, run.repeat_index)
            self.assertEqual(parsed.seed, run.seed)

    def test_yaml_workloads_match_split_policy(self):
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            set(config["workloads"]),
            set(DEFAULT_SPLIT_POLICY.seen_workloads)
            | set(DEFAULT_SPLIT_POLICY.unseen_workloads),
        )

    def test_yaml_split_block_matches_policy(self):
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        block = config.get("split")
        if block is None:
            self.skipTest("split block is not in the YAML yet")

        self.assertEqual(block["random_shuffle"], False)
        self.assertEqual(
            tuple(block["train_repeats"]),
            DEFAULT_SPLIT_POLICY.train_repeats,
        )
        self.assertEqual(
            tuple(block["validation_repeats"]),
            DEFAULT_SPLIT_POLICY.validation_repeats,
        )
        self.assertEqual(
            tuple(block["test_repeats"]),
            DEFAULT_SPLIT_POLICY.test_repeats,
        )
        self.assertEqual(
            tuple(block["unseen_workloads"]),
            DEFAULT_SPLIT_POLICY.unseen_workloads,
        )


if __name__ == "__main__":
    unittest.main()
