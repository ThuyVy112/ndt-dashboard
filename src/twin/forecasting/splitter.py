from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Split names. UNSEEN is a held-out workload family, not a fourth random slice.
TRAIN = "train"
VALIDATION = "validation"
TEST = "test"
UNSEEN = "unseen"
SPLIT_NAMES = (TRAIN, VALIDATION, TEST, UNSEEN)

# Run id contract: {workload}-r{NN}-s{seed}, e.g. stable-r01-s101.
# The workload may contain "-" (hot-switch), so the pattern is anchored on the
# trailing "-rNN-sSEED" instead of splitting the id on every "-".
_RUN_ID_PATTERN = re.compile(
    r"^(?P<workload>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)"
    r"-r(?P<repeat>\d{2})-s(?P<seed>\d+)$"
)


@dataclass(frozen=True)
class ParsedRunId:
    workload: str
    repeat: int
    seed: int


def build_run_id(workload: str, repeat: int, seed: int) -> str:
    return f"{workload}-r{repeat:02d}-s{seed}"


def parse_run_id(run_id: str) -> ParsedRunId:
    match = _RUN_ID_PATTERN.match(run_id)
    if match is None:
        raise ValueError(
            f"run_id {run_id!r} does not match {{workload}}-rNN-sSEED"
        )

    return ParsedRunId(
        workload=match.group("workload"),
        repeat=int(match.group("repeat")),
        seed=int(match.group("seed")),
    )


@dataclass(frozen=True)
class SplitPolicy:
    """Frozen run-level split strategy.

    Splitting is by whole run, never by row. Samples one second apart are
    nearly identical, so a row-level (or shuffled) split would leak the test
    set into training.
    """

    train_repeats: tuple[int, ...] = (1, 2, 3)
    validation_repeats: tuple[int, ...] = (4,)
    test_repeats: tuple[int, ...] = (5,)
    seen_workloads: tuple[str, ...] = (
        "stable",
        "gradual",
        "burst",
        "oscillating",
    )
    unseen_workloads: tuple[str, ...] = ("hot-switch",)
    random_shuffle: bool = False

    def __post_init__(self) -> None:
        if self.random_shuffle:
            raise ValueError(
                "random_shuffle must be False: it would mix runs across splits"
            )

        repeat_sets = (
            set(self.train_repeats),
            set(self.validation_repeats),
            set(self.test_repeats),
        )
        if sum(len(item) for item in repeat_sets) != len(
            set().union(*repeat_sets)
        ):
            raise ValueError("train/validation/test repeats must not overlap")

        if set(self.seen_workloads) & set(self.unseen_workloads):
            raise ValueError(
                "a workload cannot be both seen and unseen"
            )


DEFAULT_SPLIT_POLICY = SplitPolicy()


@dataclass(frozen=True)
class SplitAssignment:
    train: tuple[str, ...]
    validation: tuple[str, ...]
    test: tuple[str, ...]
    unseen: tuple[str, ...]

    def as_dict(self) -> dict[str, tuple[str, ...]]:
        return {
            TRAIN: self.train,
            VALIDATION: self.validation,
            TEST: self.test,
            UNSEEN: self.unseen,
        }


def assign_split(
    run_id: str,
    policy: SplitPolicy = DEFAULT_SPLIT_POLICY,
) -> str:
    """Return the split of one run. Unknown runs raise; nothing is dropped."""
    parsed = parse_run_id(run_id)

    # Unseen workloads are checked first so they can never reach train/val/test.
    if parsed.workload in policy.unseen_workloads:
        return UNSEEN

    if parsed.workload not in policy.seen_workloads:
        raise ValueError(f"unknown workload in run_id {run_id!r}")

    if parsed.repeat in policy.train_repeats:
        return TRAIN
    if parsed.repeat in policy.validation_repeats:
        return VALIDATION
    if parsed.repeat in policy.test_repeats:
        return TEST

    raise ValueError(f"repeat is not assigned to a split: {run_id!r}")


def assert_no_leakage(assignment: SplitAssignment) -> None:
    """Raise if any run_id appears in more than one split."""
    owner: dict[str, str] = {}

    for split_name, run_ids in assignment.as_dict().items():
        for run_id in run_ids:
            if run_id in owner:
                raise ValueError(
                    f"run_id {run_id!r} appears in both "
                    f"{owner[run_id]} and {split_name}"
                )
            owner[run_id] = split_name


def split_run_ids(
    run_ids: Iterable[str],
    policy: SplitPolicy = DEFAULT_SPLIT_POLICY,
) -> SplitAssignment:
    """Split run ids deterministically (sorted, independent of input order)."""
    buckets: dict[str, list[str]] = {name: [] for name in SPLIT_NAMES}

    for run_id in sorted(set(run_ids)):
        buckets[assign_split(run_id, policy)].append(run_id)

    assignment = SplitAssignment(
        train=tuple(buckets[TRAIN]),
        validation=tuple(buckets[VALIDATION]),
        test=tuple(buckets[TEST]),
        unseen=tuple(buckets[UNSEEN]),
    )
    assert_no_leakage(assignment)
    return assignment


def split_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    run_id_key: str = "run_id",
    policy: SplitPolicy = DEFAULT_SPLIT_POLICY,
) -> dict[str, list[Mapping[str, Any]]]:
    """Group sample rows by the split of their run, keeping original order."""
    result: dict[str, list[Mapping[str, Any]]] = {
        name: [] for name in SPLIT_NAMES
    }

    for row in rows:
        result[assign_split(str(row[run_id_key]), policy)].append(row)

    return result


def split_frame(
    frame: Any,
    *,
    run_id_column: str = "run_id",
    policy: SplitPolicy = DEFAULT_SPLIT_POLICY,
) -> dict[str, Any]:
    """Same as split_rows for a pandas DataFrame (pandas is not imported here)."""
    labels = frame[run_id_column].map(
        lambda value: assign_split(str(value), policy)
    )

    # Boolean masks keep the original row order, so nothing is shuffled.
    return {name: frame[labels == name] for name in SPLIT_NAMES}
