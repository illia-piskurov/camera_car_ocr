from __future__ import annotations

import argparse

from .config import Settings
from .orchestrator import run_camera_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single camera worker")
    parser.add_argument("--camera-id", type=int, required=True)
    args = parser.parse_args()
    run_camera_worker(args.camera_id, settings=Settings.from_env())


if __name__ == "__main__":
    main()
