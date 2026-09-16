from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def git_commit(repo_root: Path) -> str:
    result = subprocess.run(
        [
            "git",
            "rev-parse",
            "HEAD",
        ],
        cwd=str(repo_root),
        check=True,
        text=True,
        capture_output=True,
    )

    return result.stdout.strip()


def make_run_id(
    experiment_type: str,
    controller_id: str,
    rate: float,
    repeat_index: int,
) -> str:
    if float(rate).is_integer():
        rate_text = str(int(rate))
    else:
        rate_text = str(rate).replace(".", "p")

    return (
        f"{experiment_type}-"
        f"{controller_id}-"
        f"{rate_text}-"
        f"r{repeat_index:02d}"
    )

# not overriding existing run dir, so that we don't accidentally overwrite previous runs
def create_run_dir(
    output_root: Path,
    run_id: str,
) -> Path:
    run_dir = output_root / run_id

    if run_dir.exists():
        raise FileExistsError(
            f"run already exists: {run_dir}"
        )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    (run_dir / "logs").mkdir()

    return run_dir


def write_json(
    path: Path,
    payload: Dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            payload,
            stream,
            ensure_ascii=False,
            indent=2,
        )

        stream.write("\n")


def append_jsonl(
    path: Path,
    payload: Dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as stream:
        stream.write(
            json.dumps(
                payload,
                ensure_ascii=False,
            )
            + "\n"
        )


def restore_sudo_owner(
    path: Path,
) -> None:
    uid_text = os.getenv("SUDO_UID")
    gid_text = os.getenv("SUDO_GID")

    if uid_text is None or gid_text is None:
        return

    uid = int(uid_text)
    gid = int(gid_text)
    chown = getattr(os, "chown", None)

    if chown is None:
        return

    for current in [path] + list(
        path.rglob("*")
    ):
        try:
            chown(
                current,
                uid,
                gid,
            )
        except FileNotFoundError:
            pass