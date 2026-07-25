"""Continuously score newly written CICFlowMeter flow rows.

Run this in a separate PowerShell window while CICFlowMeter is capturing.
The watcher polls the CICFlowMeter daily output directory and scores each new
flow once with the saved multiclass Random Forest model.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import joblib
import pandas as pd

from ids_scoring import score_multiclass


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "models" / "cicids2017_multiclass_random_forest.joblib"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_CAPTURE_DIR = Path(r"C:\Project\CICFlowMeter-master\data\daily")
STATE_PATH = OUTPUT_DIR / "live_watcher_state.json"
STATUS_PATH = OUTPUT_DIR / "live_watcher_status.json"
PREDICTIONS_PATH = OUTPUT_DIR / "live_flow_predictions.csv"


def latest_flow_file(capture_dir: Path) -> Path | None:
    files = list(capture_dir.glob("*_Flow.csv"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def load_state() -> dict[str, int]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def append_predictions(result: pd.DataFrame) -> None:
    header = not PREDICTIONS_PATH.exists()
    result.to_csv(PREDICTIONS_PATH, mode="a", header=header, index=False)


def process_once(capture_dir: Path, bundle: dict, state: dict[str, int]) -> int:
    flow_file = latest_flow_file(capture_dir)
    if flow_file is None:
        write_json(STATUS_PATH, {
            "status": "Waiting for a CICFlowMeter *_Flow.csv file",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return 0

    try:
        raw = pd.read_csv(flow_file, low_memory=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, PermissionError):
        # CICFlowMeter may be writing the file at this exact moment. Retry next poll.
        return 0

    key = str(flow_file.resolve())
    last_row = state.get(key, 0)
    if len(raw) < last_row:  # A new capture overwrote or restarted the file.
        last_row = 0
    new_rows = raw.iloc[last_row:].copy()
    state[key] = len(raw)
    write_json(STATE_PATH, state)

    if new_rows.empty:
        write_json(STATUS_PATH, {
            "status": "Watching for new flows",
            "capture_file": str(flow_file),
            "total_rows_seen": len(raw),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return 0

    result, missing = score_multiclass(new_rows, bundle)
    result.insert(0, "Capture File", flow_file.name)
    result.insert(1, "Flow Row", range(last_row + 1, len(raw) + 1))
    result.insert(2, "Scored At UTC", datetime.now(timezone.utc).isoformat())
    append_predictions(result)

    alerts = int(result["Requires Review"].eq("Yes").sum())
    write_json(STATUS_PATH, {
        "status": "Watching for new flows",
        "capture_file": str(flow_file),
        "total_rows_seen": len(raw),
        "last_batch_flows": len(result),
        "last_batch_alerts": alerts,
        "missing_features": missing,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"Scored {len(result)} new flow(s) from {flow_file.name}; alerts: {alerts}")
    return len(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch CICFlowMeter output and score new flows.")
    parser.add_argument("--capture-dir", type=Path, default=DEFAULT_CAPTURE_DIR)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--once", action="store_true", help="Process currently available new rows once, then exit.")
    args = parser.parse_args()

    if not args.capture_dir.exists():
        raise FileNotFoundError(f"Capture directory not found: {args.capture_dir}")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Multiclass model not found: {MODEL_PATH}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    bundle = joblib.load(MODEL_PATH)
    state = load_state()
    print(f"Watching: {args.capture_dir}")
    print("Using model: multiclass Random Forest")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            process_once(args.capture_dir, bundle, state)
            if args.once:
                break
            time.sleep(max(args.poll_seconds, 1.0))
    except KeyboardInterrupt:
        print("\nLive watcher stopped.")


if __name__ == "__main__":
    main()
